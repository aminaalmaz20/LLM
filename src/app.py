import os
import logging
from typing import List

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request

# Загружаем переменные окружения из файла .env (если он есть).
load_dotenv()

# Настройка логирования — полезно при отладке и для QA-инженеров.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Примечание: приложение больше не ожидает API-ключа в переменных окружения.
# В продакшене при необходимости авторизации добавьте её отдельно.
# Для тестов и совместимости возвращаем чтение ключа из окружения.
MENTORPIECE_API_KEY = os.getenv("MENTORPIECE_API_KEY")
if not MENTORPIECE_API_KEY:
    logger.info("MENTORPIECE_API_KEY not set in environment.")

# Допустимые языки для перевода — если выбран иной, вернём 400 Bad Request.
ALLOWED_LANGUAGES = {'English', 'French', 'German'}

# Константа: endpoint внешнего API, указан в техническом задании.
MENTORPIECE_ENDPOINT = "https://api.mentorpiece.org/v1/process-ai-request"

# Режим моков: если установлено в 'true', приложение будет возвращать
# фиктивные ответы вместо реальных сетевых вызовов. Удобно для локального
# тестирования, когда внешний API недоступен или ключ недействителен.
MOCK_MENTORPIECE = os.getenv("MOCK_MENTORPIECE", "false").lower() == "true"

def call_llm(model_name: str, messages: List[str]) -> str:
    """
    Вспомогательная функция для вызова LLM через HTTP POST.

    Аргументы:
    - model_name: str — имя модели, используемой на сервере LLM.
    - messages: List[str] — список сообщений/частей промпта. Мы объединяем их
      в один текст для отправки в поле `prompt` API.

    Возвращает:
    - str — текстовый ответ модели. В случае ошибки возвращается
      подробное сообщение об ошибке (тоже как строка), чтобы UI мог отобразить его.

    Обработка ошибок:
    - Ловим сетевые ошибки и ошибки HTTP (4xx/5xx) и логируем их.
    - Ограничение по таймауту: 15 секунд — практичный выбор для UI.
    """

    # Если включён mock-режим — возвращаем фиктивный ответ без сетевого вызова.
    if MOCK_MENTORPIECE:
        prompt_sample = messages[0] if messages else ""
        model_lower = model_name.lower()
        # Для моделей перевода возвращаем наглядный "перевод" с фрагментом входа.
        if 'qwen' in model_lower:
            short = prompt_sample.split('\n\n')[-1][:300]
            return f"(mock) Перевод: {short} ..."
        # Для модели-оценщика возвращаем пример оценки с аргументацией.
        if 'claude' in model_lower or 'judge' in model_lower:
            return "(mock) Оценка: 8/10. Аргументация: перевод адекватен, но требует стилистической правки."
        # Универсальный мок для прочих моделей
        return f"(mock) Ответ модели {model_name}: {prompt_sample[:200]}..."

    # Собираем единый текстовый промпт из списка сообщений.
    prompt_text = "\n\n".join(messages)

    payload = {
        "model_name": model_name,
        "prompt": prompt_text,
    }

    # Заголовки: всегда указываем Content-Type; при наличии ключа добавляем Authorization.
    headers = {
        "Content-Type": "application/json",
    }
    if MENTORPIECE_API_KEY:
        headers["Authorization"] = f"Bearer {MENTORPIECE_API_KEY}"

    try:
        # Выполняем POST-запрос к API.
        resp = requests.post(MENTORPIECE_ENDPOINT, json=payload, headers=headers, timeout=15)

        # Если пришёл код ошибки, выбрасываем исключение для обработки ниже.
        resp.raise_for_status()

        # Ожидаем JSON-ответ в формате {"response": "..."}
        data = resp.json()
        return data.get("response", "")

    except requests.exceptions.RequestException as e:
        # Логируем полную информацию для QA/разработчиков,
        # возвращаем пользователю краткое и понятное сообщение.
        logger.exception("Ошибка при вызове MENTORPIECE API: %s", e)
        return f"Ошибка при обращении к LLM: {str(e)}"


# Создаём Flask-приложение.
app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    """
    GET / — рендерит форму ввода.

    Возвращаем шаблон index.html с пустыми полями.
    """

    return render_template('index.html', original_text='', translation='', evaluation='', language='English')


@app.route('/', methods=['POST'])
def handle_form():
    """
    POST / — принимает форму, выполняет перевод и последующую оценку.

    Алгоритм:
    1. Получаем исходный текст и выбранный язык из формы.
    2. Формируем промпт для модели перевода (Qwen/Qwen3-VL-30B-A3B-Instruct).
    3. Вызываем call_llm для получения перевода.
    4. Формируем промпт для модели-оценщика (claude-sonnet-4-5-20250929).
    5. Вызываем call_llm для получения вердикта и отображаем результат.

    Комментарии для QA:
    - Если LLM вернул сообщение об ошибке (строка, начинающаяся с "Ошибка"),
      оно будет показано в поле перевода или оценки — это упрощённый подход
      для дебага UI.
    """

    # Берём данные из формы
    original_text = request.form.get('original_text', '').strip()
    language = request.form.get('language', 'English')

    # Простая валидация: если текст пустой — рендерим обратно с сообщением.
    # Проверяем пустой текст или только пробелы
    if not original_text:
        error_msg = 'Пожалуйста, введите текст для перевода.'
        return render_template('index.html', original_text='', translation=error_msg, evaluation=''), 400

    # Проверка длины
    if len(original_text) > 5000:
        error_msg = 'Слишком длинный текст для перевода (макс. 5000 символов).'
        return render_template('index.html', original_text='', translation=error_msg, evaluation=''), 400

    # Проверка поддерживаемого языка
    if language not in ALLOWED_LANGUAGES:
        error_msg = f'Язык "{language}" не поддерживается.'
        return render_template('index.html', original_text='', translation=error_msg, evaluation=''), 400

    # Шаг 1: перевод
    # Формируем понятный промпт — чем яснее инструкция, тем предсказуемее ответ LLM.
    translate_prompt = f"Переведи следующий текст на {language}:\n\n{original_text}"

    # Вызов модели перевода (по заданию — Qwen/Qwen3-VL-30B-A3B-Instruct)
    translation = call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', [translate_prompt])

    # Шаг 2: оценка качества перевода
    # Промпт явно просит дать оценку от 1 до 10 и аргументацию.
    evaluation_prompt = (
        "Оцени качество перевода от 1 до 10 и аргументируй.\n\n"
        f"Оригинал:\n{original_text}\n\nПеревод:\n{translation}"
    )

    evaluation = call_llm('claude-sonnet-4-5-20250929', [evaluation_prompt])

    # Рендерим страницу с исходником, переводом и оценкой.
    return render_template('index.html', original_text=original_text, translation=translation, evaluation=evaluation)


if __name__ == '__main__':
    # Запуск приложения локально для разработки.
    # Обычно в продакшене используют WSGI-сервер (gunicorn/uvicorn и т.п.).
    app.run(host='0.0.0.0', port=5000, debug=True)
