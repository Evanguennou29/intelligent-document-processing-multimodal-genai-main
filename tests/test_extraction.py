"""Robust parsing of whatever the model decides to return."""

from __future__ import annotations

import pytest

from idp.errors import ExtractionError
from idp.extraction.llm_extractor import (
    extract_json_object,
    first_json_object,
    strip_code_fence,
)


def test_plain_object() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_fenced_object() -> None:
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_object_surrounded_by_prose() -> None:
    raw = 'Here is the extraction you asked for:\n{"a": 1, "b": {"c": 2}}\nHope it helps!'
    assert extract_json_object(raw) == {"a": 1, "b": {"c": 2}}


def test_trailing_comma_is_repaired() -> None:
    assert extract_json_object('{"a": 1, "b": [1, 2,], }') == {"a": 1, "b": [1, 2]}


def test_braces_inside_strings_do_not_break_the_scan() -> None:
    raw = '{"note": "value with } inside", "b": 2}'
    assert extract_json_object(raw) == {"note": "value with } inside", "b": 2}


def test_escaped_quote_inside_string() -> None:
    raw = r'{"note": "a \" b", "b": 2}'
    assert extract_json_object(raw)["b"] == 2


@pytest.mark.parametrize("raw", ["", "   ", "no json at all", "[1, 2, 3]", None])
def test_unusable_payloads_raise(raw) -> None:
    with pytest.raises(ExtractionError):
        extract_json_object(raw)


def test_strip_code_fence_without_fence() -> None:
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'


def test_first_json_object_returns_none_when_absent() -> None:
    assert first_json_object("nothing here") is None
