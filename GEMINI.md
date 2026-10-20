# OCIO Config Minification - AI Agent Instructions

This repository uses modern Python packaging and strict development standards. When operating within this workspace, AI agents must adhere to the following rules:

## 1. Code Architecture & Layout

- **Source Layout**: The project uses a `src/ocio_minifier` layout. Do not create scripts at the repository root.
- **Protocol-Driven**: Minification transformations must implement the `Transform` protocol (`src/ocio_minifier/transforms/base.py`) with `name`, `description`, `is_lossy`, and `apply(content: str) -> str`.
- **Lossy vs. Lossless**: Any transformation that alters mathematical output or removes meaningful configuration data (e.g., descriptions, numerical precision rounding) MUST be marked as `is_lossy = True`. Lossy transforms must be strictly opt-in via CLI flags or the `aggressive` preset.

## 2. Code Quality & Formatting

- **Linter**: Use `ruff` (`ruff check .` and `ruff format .`). Code must pass all checks and be formatted before committing.
- **Typing**: The package is PEP 561 compliant (`py.typed`). All functions and methods must have strict type hints. Validate with `mypy .`.
- **Security**: Run `bandit -c pyproject.toml -r .` to ensure no security vulnerabilities are introduced.
- **Markdown**: Validate documentation using `pre-commit run markdownlint --all-files`.

## 3. Testing & Coverage

- **Framework**: Use `pytest`.
- **Coverage**: The repository enforces a strict test coverage minimum (>= 95%).
- **Rules**:
  - Every new transform must have a dedicated unit test file in `tests/`.
  - Transforms must be tested for protocol conformance, idempotency, and parity via `tests/test_transforms.py`.
  - Ensure tests cover PyOpenColorIO validation and numerical DAG fidelity verification.

## 4. Git & Commits

- **Conventional Commits**: Use conventional commit messages (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `ci:`).
- **Commit Signing**: All commits MUST be signed using GPG (`git commit -S -s`). Ensure the correct author identity and signing key are utilized.
- **Pre-commit**: The repository uses `pre-commit`. Hooks must pass before a commit is considered complete.
