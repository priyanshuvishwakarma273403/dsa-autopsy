# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-24

### Added
- **Project Structure**: Organized codebase following Clean Architecture principles (Domain, Application, Infrastructure layers).
- **Core Abstractions**: Defined `BaseParser`, `BaseExecutor`, `BaseAnalyzer`, and `BaseExplainer` interfaces to decouple application logic from concrete drivers.
- **Service Orchestrator**: Implemented the central `AutopsyOrchestrator` to coordinate solution parsing, execution, trace analysis, and report generation.
- **Domain Models**: Defined immutable entities (`SourceCode`, `SolutionTestCase`, `ExecutionResult`, `TraceFrame`, `Invariant`, `Violation`, `AutopsyReport`).
- **Telemetry System**: Created structured JSON logging handlers to support production logging sinks.
- **Configuration Engine**: Integrated Pydantic Settings supporting typed parameters, environment overrides, and dotenv (`.env`) loading.
- **Testing Infrastructure**: Wired up a robust PyTest suite with markers (`unit`, `integration`, `e2e`) and 100% type-checked mock orchestrator runs.
- **Developer Tooling**: Configured pre-commit hooks containing Ruff formatting/linting and strict MyPy static analysis.
