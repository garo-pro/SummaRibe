import importlib
from pathlib import Path

import pytest

from summaribe.core.exceptions import ProviderUnavailableError, RegistryError
from summaribe.transcription.custom import SUPPORTED_ARCHITECTURES, create_custom_provider
from summaribe.transcription.registry import (
    create_provider,
    get_provider_class,
    list_provider_classes,
)


def test_builtin_providers_are_registered():
    ids = {cls.id for cls in list_provider_classes()}
    assert ids == {"whisper", "parakeet", "qwen3_asr"}


def test_unknown_provider_raises():
    with pytest.raises(RegistryError):
        get_provider_class("does-not-exist")


def test_create_provider_instantiates_with_config():
    provider = create_provider("whisper", model="tiny")
    assert provider.model_name_or_path == "tiny"


# The heavy ML extras are optional, so these tests follow the environment they
# run in rather than assuming the dependency is missing.
_PROVIDER_MODULES = {
    "whisper": ("faster_whisper",),
    "parakeet": ("nemo.collections.asr",),
    "qwen3_asr": ("soundfile", "torch", "transformers"),
}


def _importable(modules: tuple[str, ...]) -> bool:
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            return False
    return True


@pytest.mark.parametrize("provider_id,modules", sorted(_PROVIDER_MODULES.items()))
def test_provider_availability_tracks_its_dependency(provider_id: str, modules: tuple[str, ...]):
    provider = create_provider(provider_id)
    assert provider.is_available() is _importable(modules)


def test_transcribe_without_dependency_raises_provider_unavailable(tmp_path: Path):
    if _importable(_PROVIDER_MODULES["whisper"]):
        pytest.skip("faster-whisper is installed; nothing to be unavailable")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"not-real-audio")
    provider = create_provider("whisper", model="tiny")
    with pytest.raises(ProviderUnavailableError):
        provider.transcribe(audio)


def test_custom_provider_rejects_unknown_architecture(tmp_path: Path):
    with pytest.raises(RegistryError):
        create_custom_provider("not-an-architecture", tmp_path / "model.bin")


def test_custom_provider_maps_architecture_to_model_path(tmp_path: Path):
    model_path = tmp_path / "model.bin"
    for architecture in SUPPORTED_ARCHITECTURES:
        provider = create_custom_provider(architecture, model_path)
        assert provider.model_name_or_path == str(model_path)
