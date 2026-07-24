# dsa-autopsy

[![CI](https://github.com/priyanshuvishwakarma273403/dsa-autopsy/actions/workflows/ci.yml/badge.svg)](https://github.com/priyanshuvishwakarma273403/dsa-autopsy/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

An AI-powered algorithm debugging engine designed to analyze code failures, identify violated invariants, pinpoint invalid assumptions, and explain execution path bugs.

---

## 🎯 Project Goal

When developers or student solutions fail competitive programming or algorithm problems, traditional tools only return a simple feedback like "Wrong Answer on Test 4". `dsa-autopsy` aims to go beyond detection and provide a full **post-mortem autopsy** of the solution:
1. **Explain the Failure**: Explain why the code failed in plain, human-readable terms.
2. **Locate Edge Cases**: Identify what input boundaries caused the execution state to diverge.
3. **Pinpoint Invariants**: Discover loops or functional invariants that were broken.
4. **Invalid Assumptions**: Identify logic lines where developer assumptions (e.g. index limits, type bounds) proved false.
5. **Trace the Bug**: Render the exact execution path leading to the bug.

`dsa-autopsy` forms the base intelligence backend of the **DSA Collective** ecosystem.

---

## 🏗️ Architecture

This repository strictly adheres to **Clean Architecture** principles:

```
               ┌──────────────────────────────┐
               │         Infrastructure       │
               │  (FastAPI, CLI, LLM Clients) │
               └──────────────┬───────────────┘
                              │ (Depends on)
                              ▼
               ┌──────────────────────────────┐
               │          Application         │
               │   (Orchestrator, Interfaces) │
               └──────────────┬───────────────┘
                              │ (Depends on)
                              ▼
               ┌──────────────────────────────┐
               │            Domain            │
               │ (Entities, Custom Exceptions)│
               └──────────────────────────────┘
```

- **Domain Layer (`src/dsa_autopsy/models` & `exceptions`)**: Core dataclasses (`SourceCode`, `TestCase`, `TraceFrame`, etc.) and system exceptions. Completely decoupled from external frameworks.
- **Application Layer (`src/dsa_autopsy/interfaces` & `services`)**: Abstract interface contracts (e.g. `BaseParser`, `BaseExecutor`) and the central orchestrator coordinating the workflow.
- **Infrastructure Layer (`src/dsa_autopsy/config` & `telemetry`)**: External adapters, logging configuration, and environment setups.

See [Architecture & Extension Guide](docs/architecture.md) for detailed descriptions on how to implement concrete Tree-sitter parsers, LLM explainers, and API wrappers.

---

## 📂 Folder Structure

```
dsa-autopsy/
├── .github/                 # GitHub CI workflows and templates
├── assets/                  # Branding assets and diagrams
├── docs/                    # Architectural documents and design guides
├── examples/                # Runnable demonstration scripts
├── scripts/                 # Bootstrap and developer helper scripts
├── src/
│   └── dsa_autopsy/
│       ├── analyzers/       # Invariant and failure trace analyzers
│       ├── config/          # Pydantic configuration settings
│       ├── exceptions/      # Custom domain exceptions
│       ├── explainers/      # LLM and rule-based diagnostic generators
│       ├── interfaces/      # Loose coupling abstract contracts (ABCs)
│       ├── models/          # Immutable domain data structures (dataclasses)
│       ├── parsers/         # Source code and AST parsers
│       ├── reports/         # Report compilers (JSON, Markdown, HTML)
│       ├── services/        # Orchestrator coordinating core workflow
│       ├── telemetry/       # Structured logging & metrics setup
│       ├── utils/           # Shared helper functions
│       └── py.typed         # PEP 561 compliance marker
├── tests/                   # Pytest suite (unit, integration, e2e)
├── .editorconfig            # Indentation and format settings
├── .gitignore               # Ignored files list
├── .pre-commit-config.yaml  # Formatter, linter and type-checking hooks
├── pyproject.toml           # Project metadata and tooling parameters
└── README.md                # Project landing documentation
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12 or 3.13
- [uv](https://github.com/astral-sh/uv) (Preferred) or `pip` (Python virtualenv)

### Installation & Developer Setup

To bootstrap the local development environment (including sync of dependencies, setting up pre-commit hooks, and verifying setup with tests), run the setup script:

```bash
python scripts/setup_dev.py
```

Or using `uv` directly:

```bash
uv run scripts/setup_dev.py
```

### Running the Demo

To execute the bundled mockup autopsy session demonstrating the service orchestrator flow:

```bash
uv run examples/run_basic_autopsy.py
```

---

## 🛠️ Development

### Configuration

Configuration parameters are defined in `src/dsa_autopsy/config/settings.py` and can be overridden using environment variables prefixed with `DSA_AUTOPSY_` or via a `.env` file at the root:

```bash
# Example environment configuration
DSA_AUTOPSY_ENV=production
DSA_AUTOPSY_LOG_LEVEL=DEBUG
DSA_AUTOPSY_LOG_FORMAT=json
```

### Formatting & Linting

Code formatting is enforced by [Ruff](https://github.com/astral-sh/ruff).
To lint and format files before committing:

```bash
# Run Linter
uv run ruff check .

# Run Formatter
uv run ruff format .
```

### Type Checking

Type annotations are strictly checked using [MyPy](http://mypy-lang.org/):

```bash
uv run mypy src/ tests/
```

---

## 🧪 Testing

The test suite is built on [PyTest](https://docs.pytest.org/). Tests are categorized using pytest markers:
- `unit`: Fast isolated unit checks.
- `integration`: Checks verifying components wiring.
- `e2e`: full system workflow checks.

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest -m unit

# Run with coverage report
uv run pytest --cov=src/dsa_autopsy --cov-report=html
```

---

## 🗺️ Roadmap & Future Plans

The project is structured to easily integrate the following components in future phases:
- [ ] **Multi-Language AST Parsing**: Integrate Tree-sitter for analyzing Python, Java, and C++ code.
- [ ] **Execution Tracing Engine**: Build sandboxed runners to extract local/global variable frames during execution.
- [ ] **Invariant Checker**: Implement loop invariant detection algorithms (e.g. Daikon-style analysis).
- [ ] **AI Diagnostic Explainer**: Hook up LLMs (Gemini, OpenAI, Claude) to translate program violations into rich diagnostic reports.
- [ ] **API & CLI Adapters**: Build a FastAPI web server, WebSocket channel, and gRPC endpoints to expose autopsy services to the larger DSA Collective ecosystem.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the Repository.
2. Create a Feature Branch (`git checkout -b feat/my-cool-feature`).
3. Ensure all tests, lints, and format checks pass.
4. Open a Pull Request detailing the changes using the provided PR template.

Please review our [Architecture & Extension Guide](docs/architecture.md) before making structural changes.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
