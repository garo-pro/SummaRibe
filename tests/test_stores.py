import pytest

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.exceptions import ConfigError, RegistryError


def test_provider_store_lists_packaged_defaults():
    store = ProviderStore()
    ids = {p.id for p in store.list()}
    assert {"ollama", "llamacpp", "anthropic", "openrouter", "openai"} <= ids
    for provider_id in ids:
        assert store.is_default(provider_id)


def test_all_packaged_providers_have_a_models_listing_configured():
    for provider in ProviderStore().list():
        assert provider.models is not None, f"{provider.id} should ship a models endpoint"
        assert provider.models_url is not None


def test_provider_store_user_override_shadows_default():
    store = ProviderStore()
    original = store.get("ollama")
    modified = original.model_copy(update={"name": "My Ollama"})

    store.save(modified)
    assert store.get("ollama").name == "My Ollama"
    assert store.is_default("ollama")  # still a default id, just overridden

    store.delete("ollama")
    assert store.get("ollama").name == original.name  # reverted to packaged default


def test_provider_store_delete_pure_default_without_override_fails():
    store = ProviderStore()
    with pytest.raises(ConfigError):
        store.delete("ollama")


def test_provider_store_unknown_id_raises():
    with pytest.raises(RegistryError):
        ProviderStore().get("does-not-exist")


def test_client_for_applies_stream_and_timeout_overrides():
    store = ProviderStore()
    default_config = store.get("ollama")
    assert default_config.stream is False

    client = store.client_for("ollama", stream=True, timeout_seconds=42.0)
    assert client.config.stream is True
    assert client.config.timeout_seconds == 42.0
    # the underlying stored config is untouched
    assert store.get("ollama").stream is False


def test_client_for_without_overrides_uses_stored_config():
    store = ProviderStore()
    client = store.client_for("ollama")
    assert client.config.stream is False


def test_prompt_store_lists_defaults_by_category():
    store = PromptStore()
    improve_ids = {p.id for p in store.list_by_category("improve")}
    summarize_ids = {p.id for p in store.list_by_category("summarize")}
    assert "improve_default" in improve_ids
    assert "summarize_default" in summarize_ids
    assert improve_ids.isdisjoint(summarize_ids)


def test_prompt_store_save_and_delete_user_prompt():
    from summaribe.ai.prompts import SystemPrompt

    store = PromptStore()
    prompt = SystemPrompt(id="custom-1", name="Custom", category="improve", content="Do X.")
    store.save(prompt)
    assert store.get("custom-1").content == "Do X."
    store.delete("custom-1")
    with pytest.raises(RegistryError):
        store.get("custom-1")
