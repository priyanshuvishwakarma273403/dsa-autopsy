# DSA Autopsy Architecture

This document describes the design principles and structural layers of the `dsa-autopsy` AI-powered debugging engine.

---

## 1. Clean Architecture Boundaries

To ensure `dsa-autopsy` is modular, testable, and future-proof, we strictly enforce **Clean Architecture** boundaries. Dependencies flow inward:

- **Domain Layer (`src/dsa_autopsy/models`)**: Defines the core domain entities (`SourceCode`, `SolutionTestCase`, `ExecutionResult`, `TraceFrame`, `Invariant`, `Violation`, `AutopsyReport`) as pure dataclasses free of external frameworks.
- **Application Layer (`src/dsa_autopsy/interfaces`, `services`)**:
  - **Interfaces**: Defines the abstract contracts (`BaseParser`, `BaseExecutor`, `BaseAnalyzer`, `BaseExplainer`) that enforce methods and boundaries.
  - **Orchestration**: The `AutopsyOrchestrator` implements the debugging workflow by calling these interfaces without depending on concrete execution or parsing logic.
- **Infrastructure Layer (`src/dsa_autopsy/config`, `telemetry`)**: Cross-cutting concerns such as logging setups and Pydantic configuration settings.
