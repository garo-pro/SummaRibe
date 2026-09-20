import pytest

from summaribe.ai.template_engine import extract, render, try_extract
from summaribe.core.exceptions import MissingTemplateVariableError, ResponseExtractionError


def test_render_full_token_splices_raw_value():
    template = {"messages": "{{messages}}", "stream": "{{stream}}"}
    result = render(template, {"messages": [{"role": "user", "content": "hi"}], "stream": False})
    assert result == {"messages": [{"role": "user", "content": "hi"}], "stream": False}


def test_render_inline_token_stringifies():
    result = render("Bearer {{api_key}}", {"api_key": "sk-123"})
    assert result == "Bearer sk-123"


def test_render_nested_structures():
    template = {"a": {"b": ["{{x}}", "literal", {"c": "{{y}}"}]}}
    result = render(template, {"x": 1, "y": "two"})
    assert result == {"a": {"b": [1, "literal", {"c": "two"}]}}


def test_render_missing_variable_raises():
    with pytest.raises(MissingTemplateVariableError):
        render("{{missing}}", {})


def test_render_missing_inline_variable_raises():
    with pytest.raises(MissingTemplateVariableError):
        render("prefix {{missing}} suffix", {})


def test_render_dotted_lookup():
    result = render("{{a.b.c}}", {"a": {"b": {"c": 42}}})
    assert result == 42


def test_extract_dotted_path_with_list_index():
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert extract(data, "choices.0.message.content") == "hello"


def test_extract_missing_path_raises():
    with pytest.raises(ResponseExtractionError):
        extract({"a": {}}, "a.b.c")


def test_try_extract_returns_none_on_missing():
    assert try_extract({"a": {}}, "a.b.c") is None
    assert try_extract({"a": {}}, None) is None
