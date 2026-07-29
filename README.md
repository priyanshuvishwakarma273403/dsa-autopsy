# dsa-autopsy

An AI-powered algorithm debugging engine designed to analyze code failures, identify violated invariants, pinpoint invalid assumptions, and explain execution path bugs.

## Installation

```bash
pip install -e ".[dev]"
```

## Development

To format the code, run:
```bash
python -m ruff format src tests
```

To run lint checks:
```bash
python -m ruff check src tests
```

To run type checking:
```bash
python -m mypy src tests
```

## Testing

To run the test suite:
```bash
python -m pytest
```

## License

This project is licensed under the MIT License.
