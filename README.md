# dsa-autopsy

An AI-powered algorithm debugging engine designed to analyze code failures, identify violated invariants, pinpoint invalid assumptions, and explain execution path bugs.

---

## 🎯 Project Goal

When developer solutions fail algorithm problems, traditional tools only return feedback like "Wrong Answer". `dsa-autopsy` aims to provide a detailed post-mortem autopsy:
1. **Explain the Failure**: Explain why the code failed in plain, human-readable terms.
2. **Locate Edge Cases**: Identify what input boundaries caused the execution state to diverge.
3. **Pinpoint Invariants**: Discover loops or functional invariants that were broken.
4. **Invalid Assumptions**: Identify logic lines where developer assumptions proved false.
5. **Trace the Bug**: Render the exact execution path leading to the bug.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12 or 3.13
- [uv](https://github.com/astral-sh/uv) (Preferred) or standard virtualenv

### Installation & Developer Setup

To bootstrap the local development environment, run the setup script:

```bash
python scripts/setup_dev.py
```

### Running Tests

The test suite is built on pytest. To run all checks locally:

```bash
uv run pytest
```

To run linting and type checking:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
