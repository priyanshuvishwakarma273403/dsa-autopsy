# Contributing to dsa-autopsy

Thank you for your interest in contributing to `dsa-autopsy`! We welcome community contributions to build a state-of-the-art AI-powered debugging engine.

---

## 🛠️ Development Setup

We use [uv](https://github.com/astral-sh/uv) to manage dependencies and virtual environments.

1. **Fork and Clone** the repository.
2. **Initialize Environment & Tooling**:
   ```bash
   python scripts/setup_dev.py
   ```
   This will install all project dependencies, register pre-commit git hooks, and run all verification tests.

---

## 📐 Coding Standards & Guidelines

To ensure maintenance ease, readability, and consistency across the **DSA Collective** ecosystem, we enforce strict linting and type annotations:

- **Type Annotations**: All function signatures, class members, and variables must be fully annotated. Type correctness is verified via strict **MyPy** configuration.
- **Style and Formatting**: Code formatting and linting rules are enforced using **Ruff** (Google docstring convention, 100 character line limit).
- **Clean Architecture Boundaries**:
  - Keep domain entities in `src/dsa_autopsy/models` completely pure, with no external dependencies (like Pydantic, CLI parsing libraries, or AI SDKs).
  - Define all external integrations via abstract classes in `src/dsa_autopsy/interfaces/`.

---

## 🧪 Testing Requirements

No code will be merged without corresponding test coverage.

- Write **unit tests** for utility functions and isolated business logic.
- Write **integration/e2e tests** for component wires.
- Verify tests locally before opening a pull request:
  ```bash
  uv run pytest
  ```

---

## 🚀 Pull Request Process

1. Create a branch prefixed with your task type (e.g. `feat/ast-parser`, `fix/logging-format`).
2. Implement your changes. Make sure all pre-commit hooks pass.
3. Open a Pull Request against the `main` branch.
4. Provide a clear description of the problem solved and the test verification performed in your PR description.
