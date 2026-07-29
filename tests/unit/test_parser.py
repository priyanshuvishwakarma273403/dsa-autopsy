"""Unit tests for ASTParser."""

import pytest

from dsa_autopsy.exceptions import ParsingError
from dsa_autopsy.models.domain import SourceCode
from dsa_autopsy.services.ast_parser import ASTParser


def test_ast_parser_single_function() -> None:
    """Test parsing of a source file containing a single function with a loop."""
    parser = ASTParser()
    code = SourceCode(
        content=(
            "def find_max(arr):\n"
            "    max_val = arr[0]\n"
            "    for num in arr:\n"
            "        if num > max_val:\n"
            "            max_val = num\n"
            "    return max_val\n"
        ),
        language="python",
    )
    metadata = parser.parse(code)

    assert "find_max" in metadata
    func_meta = metadata["find_max"]
    assert func_meta["name"] == "find_max"
    assert func_meta["start_line"] == 1
    assert func_meta["end_line"] == 6
    assert func_meta["arguments"] == ["arr"]
    assert len(func_meta["loops"]) == 1
    assert func_meta["loops"][0] == {
        "type": "For",
        "start_line": 3,
        "end_line": 5,
        "nesting_level": 0,
    }
    assert len(func_meta["returns"]) == 1
    assert func_meta["returns"][0] == {
        "line_number": 6,
        "value": "max_val",
    }


def test_ast_parser_multi_function() -> None:
    """Test parsing of a source file containing multiple functions."""
    parser = ASTParser()
    code = SourceCode(
        content=(
            "def square(x):\n"
            "    return x * x\n"
            "\n"
            "def sum_squares(arr):\n"
            "    total = 0\n"
            "    for num in arr:\n"
            "        total += square(num)\n"
            "    return total\n"
        ),
        language="python",
    )
    metadata = parser.parse(code)

    assert "square" in metadata
    assert "sum_squares" in metadata

    assert metadata["square"]["arguments"] == ["x"]
    assert len(metadata["square"]["loops"]) == 0

    assert metadata["sum_squares"]["arguments"] == ["arr"]
    assert len(metadata["sum_squares"]["loops"]) == 1


def test_ast_parser_nested_loops() -> None:
    """Test parsing of nested loops inside a function."""
    parser = ASTParser()
    code = SourceCode(
        content=(
            "def bubble_sort(arr):\n"
            "    n = len(arr)\n"
            "    i = 0\n"
            "    while i < n:\n"
            "        for j in range(0, n - i - 1):\n"
            "            if arr[j] > arr[j + 1]:\n"
            "                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n"
            "        i += 1\n"
        ),
        language="python",
    )
    metadata = parser.parse(code)

    assert "bubble_sort" in metadata
    loops = metadata["bubble_sort"]["loops"]
    assert len(loops) == 2

    # Outer while loop
    assert loops[0] == {
        "type": "While",
        "start_line": 4,
        "end_line": 8,
        "nesting_level": 0,
    }
    # Inner for loop
    assert loops[1] == {
        "type": "For",
        "start_line": 5,
        "end_line": 7,
        "nesting_level": 1,
    }


def test_ast_parser_unsupported_language() -> None:
    """Test that parsing an unsupported language raises ParsingError."""
    parser = ASTParser()
    code = SourceCode(
        content="public class Main {}",
        language="java",
    )
    with pytest.raises(ParsingError) as exc_info:
        parser.parse(code)
    assert "Unsupported language" in str(exc_info.value)


def test_ast_parser_syntax_error() -> None:
    """Test that parsing code with syntax errors raises ParsingError."""
    parser = ASTParser()
    code = SourceCode(
        content="def broken_func(x\n    return x\n",
        language="python",
    )
    with pytest.raises(ParsingError) as exc_info:
        parser.parse(code)
    assert "Syntax error" in str(exc_info.value)
