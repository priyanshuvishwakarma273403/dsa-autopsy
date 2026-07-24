"""Unit tests for the helper and utility modules."""

import pytest

from dsa_autopsy.utils.code_helpers import clean_source_code, strip_python_comments


@pytest.mark.unit
def test_clean_source_code() -> None:
    """Verify normalization of carriage returns and removal of trailing spaces."""
    raw_code = "def foo():  \r\n    x = 1   \r\n"
    expected = "def foo():\n    x = 1\n"
    assert clean_source_code(raw_code) == expected


@pytest.mark.unit
def test_clean_source_code_empty() -> None:
    """Verify that cleaning empty input handles returns safely."""
    assert clean_source_code("") == ""
    assert clean_source_code("\n\n") == ""


@pytest.mark.unit
def test_strip_python_comments() -> None:
    """Verify regex comment stripping for Python code."""
    raw_code = (
        'def func(x):\n    """Docstring here."""\n    y = x + 1  # inline comment\n    return y\n'
    )
    expected = "def func(x):\n\n    y = x + 1\n    return y\n"
    assert strip_python_comments(raw_code) == expected
