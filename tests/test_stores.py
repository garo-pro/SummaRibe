import pytest

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.exceptions import ConfigError, RegistryError


def test_provider_store_lists_packaged_defaults():
    store = ProviderStore()
    ids = {p.id for p in store.list()}
    assert {"ollama", "llamacpp", "anthropic", "openrouter"} <= ids
    for provider_id in ids:
        assert store.is_default(provider_id)


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
