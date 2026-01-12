# AI Translator & Critic

Простое Flask-приложение, которое использует внешний API (MENTORPIECE) для перевода текста
и оценки качества перевода.

Установка и запуск (локально):

1. Создайте виртуальное окружение и активируйте его:

```bash
python -m venv venv
source venv/bin/activate
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example` и добавьте ваш ключ:

```text
MENTORPIECE_API_KEY=ваш_ключ
```

4. Запустите приложение:

```bash
export FLASK_APP=src.app
flask run
```

Откройте http://127.0.0.1:5000

Файлы:
- [src/app.py](src/app.py) — основная логика приложения.
- [src/templates/index.html](src/templates/index.html) — HTML шаблон.
- [requirements.txt](requirements.txt) — зависимости.
- [.env.example](.env.example) — пример переменных окружения.
# LLM
