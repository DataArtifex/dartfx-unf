# Contributing to dartfx-unf

Thank you for your interest in contributing! We welcome all types of contributions, from bug reports and documentation improvements to new features and bug fixes.

By participating in this project, you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Maintainers
- **Pascal Heus** ([@kulnor](https://github.com/kulnor))

## Development Workflow

This project uses **uv** for dependency management and **Hatch** for project orchestration.

### 1. Environment Setup
Clone the repository and install dependencies:
```bash
uv sync
uv run pre-commit install
```

### 2. Standards
- **Linting & Formatting**: We use [Ruff](https://beta.astral-sh/ruff/). Run `uv run ruff check .` and `uv run ruff format .` before committing.
- **Type Checking**: We use [Mypy](http://mypy-lang.org/). Run `hatch run types:check`.
- **Testing**: We use [Pytest](https://docs.pytest.org/). Run `uv run pytest`.

## Contribution Process

1. **Find an Issue**: Look for open issues or create a new one to discuss your proposed changes.
2. **Branch**: Create a new branch for your work: `git checkout -b feature/your-feature-name`.
3. **Develop**: Implement your changes, including tests and documentation updates.
4. **Validate**: Ensure all tests pass and linting is clean.
5. **Pull Request**: Submit a Pull Request to the `main` branch.

## Documentation
- Documentation is located in `docs/source`.
- Build the docs locally using `hatch run docs:build`.
- Ensure new features are documented in both the code (docstrings) and the Sphinx pages.

## Getting Help
If you have questions, feel free to open a GitHub Issue.
