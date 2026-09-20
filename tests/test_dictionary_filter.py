import pytest

from summaribe.core.exceptions import RegistryError
from summaribe.dictionary.filter import (
    Dictionary,
    DictionaryEntry,
    DictionaryStore,
    apply_dictionaries,
)


def test_entry_whole_word_replacement():
    entry = DictionaryEntry(find="k8s", replace="Kubernetes")
    dictionary = Dictionary(id="d1", name="Tech terms", entries=[entry])
    assert dictionary.apply("we run k8s in prod") == "we run Kubernetes in prod"


def test_entry_respects_whole_word_boundary():
    entry = DictionaryEntry(find="cat", replace="dog", whole_word=True)
    dictionary = Dictionary(id="d1", name="x", entries=[entry])
    assert dictionary.apply("concatenate cat") == "concatenate dog"


def test_entry_case_sensitive():
    entry = DictionaryEntry(find="Api", replace="API", case_sensitive=True)
    dictionary = Dictionary(id="d1", name="x", entries=[entry])
    assert dictionary.apply("Api api") == "API api"


def test_entries_apply_in_order():
    dictionary = Dictionary(
        id="d1",
        name="x",
        entries=[
            DictionaryEntry(find="foo", replace="bar"),
            DictionaryEntry(find="bar", replace="baz"),
        ],
    )
    assert dictionary.apply("foo") == "baz"


def test_apply_dictionaries_across_multiple():
    d1 = Dictionary(id="d1", name="x", entries=[DictionaryEntry(find="a", replace="b")])
    d2 = Dictionary(id="d2", name="y", entries=[DictionaryEntry(find="b", replace="c")])
    assert apply_dictionaries("a", [d1, d2]) == "c"


def test_store_save_list_get_delete(tmp_path):
    store = DictionaryStore(tmp_path)
    entries = [DictionaryEntry(find="x", replace="y")]
    dictionary = Dictionary(id="mine", name="Mine", entries=entries)
    store.save(dictionary)

    assert [d.id for d in store.list()] == ["mine"]
    assert store.get("mine").name == "Mine"

    store.delete("mine")
    assert store.list() == []
    with pytest.raises(RegistryError):
        store.get("mine")
