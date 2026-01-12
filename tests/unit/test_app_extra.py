# tests/unit/test_app_extra.py
# Дополнительные unit-тесты для проверки валидации, структуры запросов и обработки некорректных ответов API.

import importlib
from unittest.mock import patch, MagicMock
import pytest
import requests
import src.app as app


def make_mock_response(json_data=None, status_code=200, raise_for_status_exc=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data

    def raise_for_status():
        if raise_for_status_exc:
            raise raise_for_status_exc
        return None

    mock_resp.raise_for_status.side_effect = raise_for_status
    return mock_resp


# ---------- Validation tests ----------
def test_empty_string_returns_400(client):
    """
    Пустая строка должна приводить к HTTP 400 и сообщению об ошибке.
    """
    resp = client.post('/', data={'original_text': '', 'language': 'English'})
    assert resp.status_code == 400
    assert 'Пожалуйста, введите текст для перевода.' in resp.get_data(as_text=True)


def test_spaces_only_returns_400(client):
    resp = client.post('/', data={'original_text': '   ', 'language': 'English'})
    assert resp.status_code == 400
    assert 'Пожалуйста, введите текст для перевода.' in resp.get_data(as_text=True)


def test_too_long_text_returns_400(client):
    long_text = 'a' * 5001
    resp = client.post('/', data={'original_text': long_text, 'language': 'English'})
    assert resp.status_code == 400
    assert 'Слишком длинный текст' in resp.get_data(as_text=True)


def test_unsupported_language_returns_400(client):
    resp = client.post('/', data={'original_text': 'Hello', 'language': 'Spanish'})
    assert resp.status_code == 400
    assert 'не поддерживается' in resp.get_data(as_text=True)


# ---------- Request structure tests ----------
def test_call_llm_sends_correct_payload_and_headers(monkeypatch):
    """
    Проверяем, что call_llm формирует правильный payload и заголовки,
    включая Authorization и Content-Type.
    """
    # Установим тестовый API ключ в модуле
    monkeypatch.setenv('MENTORPIECE_API_KEY', 'TEST_KEY')
    importlib.reload(app)

    # Подготовим mock response
    mock_resp = make_mock_response(json_data={"response": "OK"}, status_code=200)

    with patch('src.app.requests.post', return_value=mock_resp) as mock_post:
        prompt = 'Hello world'
        result = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', [prompt])

        # Убедимся, что requests.post был вызван
        assert mock_post.called
        called_args, called_kwargs = mock_post.call_args
        # Первый аргумент — URL
        assert called_args[0] == app.MENTORPIECE_ENDPOINT
        # Проверяем, что в json передаётся model_name и prompt содержит исходный текст
        sent_json = called_kwargs.get('json')
        assert sent_json['model_name'] == 'Qwen/Qwen3-VL-30B-A3B-Instruct'
        assert 'Hello world' in sent_json['prompt']
        # Проверяем заголовки
        headers = called_kwargs.get('headers')
        assert headers['Content-Type'] == 'application/json'
        assert 'Authorization' in headers and 'TEST_KEY' in headers['Authorization']


# ---------- Incorrect API responses ----------
def test_status_200_but_response_absent(monkeypatch):
    mock_resp = make_mock_response(json_data={}, status_code=200)
    with patch('src.app.requests.post', return_value=mock_resp):
        res = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', ['Text'])
        # Ожидаем пустую строку, так как data.get('response', '') вернёт ''
        assert res == ''


def test_status_200_response_null(monkeypatch):
    mock_resp = make_mock_response(json_data={'response': None}, status_code=200)
    with patch('src.app.requests.post', return_value=mock_resp):
        res = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', ['Text'])
        # Если API вернул null, то функция вернёт None
        assert res is None


def test_status_429_rate_limit_returns_error_message(monkeypatch):
    http_err = requests.exceptions.HTTPError('429 Client Error: TOO MANY REQUESTS')
    mock_resp = make_mock_response(json_data={'response': 'whatever'}, status_code=429, raise_for_status_exc=http_err)
    with patch('src.app.requests.post', return_value=mock_resp):
        res = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', ['Text'])
        assert isinstance(res, str)
        assert 'Ошибка при обращении к LLM' in res


def test_timeout_exception_handled(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout('Connection timed out')

    with patch('src.app.requests.post', side_effect=raise_timeout):
        res = app.call_llm('Qwen/Qwen3-VL-30B-A3B-Instruct', ['Text'])
        assert isinstance(res, str)
        assert 'Ошибка при обращении к LLM' in res

*** End Patch