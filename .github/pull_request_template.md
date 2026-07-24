## Description

Please include a summary of the change and the related issue. Please also include relevant motivation and context. List any dependencies that are required for this change.

Fixes # (issue)

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring / Architectural cleanup

## Architecture Verification

- [ ] Code follows Clean Architecture boundaries (Infrastructure depends on Application, Application on Domain).
- [ ] No direct references to LLM API clients, fastAPI router objects, or AST parsers inside the domain layer.
- [ ] Domain models remain as pure dataclasses.
- [ ] Dependency Injection is used to pass interface implementations to orchestrator/services.

## Quality Checklist

- [ ] All functions and public classes have Google-style docstrings.
- [ ] Full static typing annotations are provided and `mypy` check passes.
- [ ] Ruff checks and format checks pass.
- [ ] Unit tests cover new code paths (run `pytest`).
- [ ] Integration or E2E tests have been added where appropriate.
