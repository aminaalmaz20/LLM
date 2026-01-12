# tests/unit/test_app.py
# Pytest unit tests для src/app.py
# Комментарии подробно объясняют, что делает каждый тест и почему.

import importlib
import types
import json
from unittest.mock import patch, MagicMock
import pytest
import os

# Импортируем модуль приложения.
# Заметьте: при импорте src.app сразу выполнится код модуля.
import src.app as app
import pytest
import pytest


def make_mock_response(json_data=None, status_code=200, raise_for_status_exc=None):
    """
    Вспомогательная функция для создания mock-объектов, имитирующих
    объект ответа от requests.post.

    - json_data: словарь, возвращаемый .json()
    - status_code: числовой HTTP-код (не обязателен, используется для ясности)
    - raise_for_status_exc: если передан, то .raise_for_status() поднимет это исключение
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}

    def raise_for_status():
        if raise_for_status_exc:
            raise raise_for_status_exc
        return None

    mock_resp.raise_for_status.side_effect = raise_for_status
    return mock_resp


# ---------- Positive Test: успешный ответ 200 OK ----------
def test_call_llm_success_translation():
    """
    Проверяем, что при успешном ответе от API функция call_llm
    возвращает ожидаемый текст из поля "response".

    Мы мокируем requests.post, чтобы:
    - не делать реальных сетевых вызовов
    - вернуть заранее подготовленный JSON
    """
    prompt = "Переведи: Привет"
    expected = "Mocked translation response"

    mock_resp = make_mock_response(json_data={"response": expected}, status_code=200)

    with patch('src.app.requests.post', return_value=mock_resp) as mock_post:
        result = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', [prompt])

        # Проверяем, что requests.post был вызван ровно 1 раз
        assert mock_post.call_count == 1

        # Проверяем, что функция вернула ровно то, что ожидали
        assert result == expected


# ---------- Environment Test: проверяем вызов os.getenv ----------
def test_environment_reads_api_key(monkeypatch):
    """
    Этот тест проверяет, что модуль приложения читает значение
    переменной окружения MENTORPIECE_API_KEY при импорте.

    Подход:
    - Создаём подмену для os.getenv, которая запоминает вызовы.
    - Перезагружаем модуль `src.app` через importlib.reload для того,
      чтобы при повторном импорте выполнилась логика чтения env.

    ВАЖНО: Тест устроен так, чтобы не требовать реального ключа, он
    лишь проверяет факт обращения к os.getenv с нужным именем.
    """
    # Сохраняем оригинальную функцию чтобы восстановить позже
    original_getenv = os.getenv

    calls = []

    def fake_getenv(name, default=None):
        calls.append((name, default))
        # возвращаем заранее известное значение для теста
        if name == 'MENTORPIECE_API_KEY':
            return 'TEST_KEY'
        return original_getenv(name, default)

    monkeypatch.setattr(os, 'getenv', fake_getenv)

    # Переимпортируем/перезагружаем модуль чтобы снова выполнить top-level код
    importlib.reload(app)

    # Проверяем, что os.getenv вызывался для MENTORPIECE_API_KEY
    assert any(call[0] == 'MENTORPIECE_API_KEY' for call in calls), "Модуль не вызывал os.getenv('MENTORPIECE_API_KEY')"

    # Также проверим, что переменная была установлена в модуле
    assert hasattr(app, 'MENTORPIECE_API_KEY')
    assert app.MENTORPIECE_API_KEY == 'TEST_KEY'


# ---------- Error Handling: симулируем ошибку сети/аутентификации ----------
def test_call_llm_handles_request_exception():
    """
    Тест проверяет, что при возникновении исключения из requests
    (например, сеть или auth) функция call_llm не падает, а возвращает
    человекочитаемое сообщение об ошибке.

    Мы мокируем requests.post так, чтобы он выбрасывал requests.exceptions.RequestException.
    """
    import requests

    def raise_request_exc(*args, **kwargs):
        raise requests.exceptions.RequestException("Connection failed")

    with patch('src.app.requests.post', side_effect=raise_request_exc):
        result = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', ["Dummy prompt"]) 

        # Ожидаем, что результат - строка с сообщением об ошибке
        assert isinstance(result, str)
        assert result.startswith('Ошибка при обращении к LLM')


# Дополнительно: тест маршрута Flask (используем test_client и мокируем call_llm)
@pytest.fixture
def client():
    """Фикстура, возвращающая Flask test client для модульных тестов маршрутов."""
    return app.app.test_client()


def test_flask_post_route_integration(monkeypatch, client):
    """
    Интеграционный unit-тест для маршрута '/' (POST).
    Мы не будем вызывать внешнее API: мокируем `call_llm`.

    Сценарий:
    - mock call_llm так, чтобы сначала вернуть перевод, затем оценку
    - используем Flask test_client для отправки POST-запроса к приложению
    - проверяем, что в ответе HTML содержатся строки перевода и оценки

    Такой тест полезен для проверки, что маршруты корректно обрабатывают
    входные данные и передают их в функцию вызова LLM.
    """
    # Мок: при первом вызове -> перевод, при втором -> оценка
    def fake_call_llm(model_name, messages):
        if 'qwen' in model_name.lower():
            return 'Translated text (mock)'
        if 'claude' in model_name.lower():
            return 'Grade: 9/10 (mock)'
        return 'Unknown model (mock)'

    monkeypatch.setattr(app, 'call_llm', fake_call_llm)

    client = app.app.test_client()

    data = {
        'original_text': 'Солнце светит.',
        'language': 'English',
    }

    response = client.post('/', data=data)
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    # Проверяем, что в отрендеренном шаблоне присутствуют mock-перевод и mock-оценка
    assert 'Translated text (mock)' in body
    assert 'Grade: 9/10 (mock)' in body
*** End Patch