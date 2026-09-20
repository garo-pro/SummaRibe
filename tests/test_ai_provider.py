import httpx
import pytest

from summaribe.ai.provider import AIClient
from summaribe.ai.schema import ProviderConfig
from summaribe.core.exceptions import ConfigError


def _openai_style_config(**overrides) -> ProviderConfig:
    base = {
        "id": "test-openai",
        "name": "Test OpenAI-compatible",
        "base_url": "http://example.test",
        "endpoint": "/v1/chat/completions",
        "request_template": {
            "model": "{{model}}",
            "messages": "{{messages}}",
            "stream": "{{stream}}",
        },
        "response_path": "choices.0.message.content",
        "stream_delta_path": "choices.0.delta.content",
        "variables": {"model": "demo-model"},
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def test_complete_non_streaming_extracts_response_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello there"}}]})

    client = AIClient(_openai_style_config())
    result = client.complete(
        system_prompt="You are helpful.",
        user_prompt="Hi",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result == "hello there"


def test_complete_sends_rendered_messages():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = AIClient(_openai_style_config())
    client.complete(
        system_prompt="sys",
        user_prompt="user text",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    body = captured["body"]
    assert body["model"] == "demo-model"
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user text"},
    ]
    assert body["stream"] is False


def test_complete_streaming_sse_accumulates_deltas():
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})

    config = _openai_style_config(stream=True)
    client = AIClient(config)
    tokens: list[str] = []
    result = client.complete(
        system_prompt="sys",
        user_prompt="hi",
        on_token=tokens.append,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result == "Hello"
    assert tokens == ["Hel", "lo"]


def test_complete_streaming_ndjson_stops_at_done():
    ndjson_body = (
        b'{"message":{"content":"Hel"},"done":false}\n'
        b'{"message":{"content":"lo"},"done":false}\n'
        b'{"message":{"content":""},"done":true}\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson_body)

    config = ProviderConfig.model_validate(
        {
            "id": "ollama-test",
            "name": "Ollama test",
            "base_url": "http://example.test",
            "endpoint": "/api/chat",
            "stream": True,
            "stream_format": "ndjson",
            "request_template": {
                "model": "{{model}}",
                "messages": "{{messages}}",
                "stream": "{{stream}}",
            },
            "response_path": "message.content",
            "stream_delta_path": "message.content",
            "stream_done_path": "done",
            "variables": {"model": "llama3.1"},
        }
    )
    client = AIClient(config)
    result = client.complete(
        system_prompt="sys",
        user_prompt="hi",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result == "Hello"


def test_missing_api_key_env_raises_config_error():
    config = _openai_style_config(api_key_env="SOME_UNSET_VAR_XYZ")
    client = AIClient(config, env={})
    with pytest.raises(ConfigError):
        client.complete(system_prompt="s", user_prompt="u")


def test_list_models_extracts_ids_from_nested_array():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b"}]})

    config = _openai_style_config(
        models={
            "endpoint": "/v1/models",
            "method": "GET",
            "response_list_path": "data",
            "model_id_path": "id",
        }
    )
    client = AIClient(config)
    models = client.list_models(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert models == ["model-a", "model-b"]


def test_list_models_supports_ollama_shaped_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200, json={"models": [{"name": "llama3:latest", "model": "llama3:latest"}]}
        )

    config = _openai_style_config(
        models={
            "endpoint": "/api/tags",
            "method": "GET",
            "response_list_path": "models",
            "model_id_path": "model",
        }
    )
    client = AIClient(config)
    models = client.list_models(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert models == ["llama3:latest"]


def test_list_models_without_config_raises_config_error():
    client = AIClient(_openai_style_config())
    with pytest.raises(ConfigError):
        client.list_models()


def test_list_models_sends_provider_auth_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-key"
        return httpx.Response(200, json={"data": []})

    config = _openai_style_config(
        api_key_env="MY_KEY",
        headers={"Authorization": "Bearer {{api_key}}"},
        models={"endpoint": "/v1/models", "response_list_path": "data", "model_id_path": "id"},
    )
    client = AIClient(config, env={"MY_KEY": "secret-key"})
    models = client.list_models(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert models == []


def test_api_key_is_available_to_header_template():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    config = _openai_style_config(
        api_key_env="MY_KEY", headers={"Authorization": "Bearer {{api_key}}"}
    )
    client = AIClient(config, env={"MY_KEY": "secret-key"})
    client.complete(
        system_prompt="s",
        user_prompt="u",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
