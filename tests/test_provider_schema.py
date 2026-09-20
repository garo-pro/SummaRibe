from summaribe.ai.schema import ModelsListConfig, ProviderConfig


def _base_config(**overrides):
    base = {
        "id": "p",
        "name": "P",
        "base_url": "http://example.test",
        "endpoint": "/chat",
        "request_template": {},
        "response_path": "text",
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


def test_models_defaults_to_none():
    config = _base_config()
    assert config.models is None
    assert config.models_url is None


def test_models_endpoint_gets_leading_slash():
    config = ModelsListConfig.model_validate({"endpoint": "v1/models"})
    assert config.endpoint == "/v1/models"


def test_models_url_combines_base_url_and_endpoint():
    config = _base_config(models={"endpoint": "/v1/models"})
    assert config.models_url == "http://example.test/v1/models"


def test_models_list_config_defaults():
    config = ModelsListConfig.model_validate({"endpoint": "/models"})
    assert config.method == "GET"
    assert config.response_list_path == "data"
    assert config.model_id_path == "id"
    assert config.request_body is None
