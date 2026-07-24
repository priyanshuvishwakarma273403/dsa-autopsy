"""Utility functions for processing and formatting code snippets."""

import re


def clean_source_code(content: str) -> str:
    """Strip basic trailing whitespaces and normalize line endings.

    Args:
        content: Raw source code string.

    Returns:
        Cleaned source code string.
    """
    # Normalize carriage return and line feed
    normalized = content.replace("\r\n", "\n")

    # Strip trailing whitespaces on each line
    lines = [line.rstrip() for line in normalized.splitlines()]

    # Re-join with single newlines, ensuring a final newline if the original had content
    if not lines or all(line == "" for line in lines):
        return ""

    return "\n".join(lines) + "\n"


def strip_python_comments(content: str) -> str:
    """Remove single-line comments and docstrings from Python source code.

    Note: This is a regex-based utility for light sanitation. Full parsing should
    use the AST/Tree-sitter parser packages.

    Args:
        content: Raw Python code.

    Returns:
        Code with comments stripped.
    """
    # Strip # style comments
    no_comments = re.sub(r"#.*", "", content)

    # Strip triple-quoted strings (multiline comments)
    no_docs = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\')', "", no_comments, flags=re.DOTALL)

    return clean_source_code(no_docs)
