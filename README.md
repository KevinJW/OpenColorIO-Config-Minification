# OCIO Config Minification

Tools and pipeline transforms for minifying OpenColorIO (OCIO) configurations while mathematically verifying pixel-level fidelity via PyOpenColorIO.

## Getting Started

### Prerequisites

- Python 3.10+ (tested with Python 3.11, 3.12, 3.13, 3.14)

### Virtual Environment Setup

Create and activate a Python virtual environment:

```powershell
# Create virtual environment
py -m venv .venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### Dependency Installation

Install the package and development dependencies:

```powershell
# Using pip with optional dependencies defined in pyproject.toml
python -m pip install --upgrade pip
python -m pip install -e .[dev]

# Alternatively via requirements-dev.txt:
python -m pip install -r requirements-dev.txt
```

### Git Pre-Commit Hooks

Install the git hook scripts:

```powershell
pre-commit install
```

## Development Tools & Best Practices

All development tools are configured directly in `pyproject.toml`:

- **Pre-commit**: Runs linting, formatting, security, and hygiene checks before each commit.
  ```powershell
  pre-commit run --all-files
  ```
- **Linting & Formatting (Ruff)**: Fast Python linter and code formatter.
  ```powershell
  ruff check .
  ruff format .
  ```
- **Type Checking (Mypy)**: Static type analysis with PyOpenColorIO support.
  ```powershell
  mypy .
  ```
- **Security Analysis (Bandit)**: Automated security vulnerability scanner.
  ```powershell
  bandit -c pyproject.toml -r .
  ```
- **Testing (Pytest)**: Unit and integration test suite.
  ```powershell
  pytest
  ```

## Project Structure

- `configs/`: Directory containing OpenColorIO configuration files, including official builtin configurations from ASWF OpenColorIO:
  - **CG Configs**:
    - `cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio`
    - `cg-config-v2.1.0_aces-v1.3_ocio-v2.3.ocio`
    - `cg-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio`
    - `cg-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio`
    - `cg-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio`
  - **Studio Configs**:
    - `studio-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio`
    - `studio-config-v2.1.0_aces-v1.3_ocio-v2.3.ocio`
    - `studio-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio`
    - `studio-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio`
    - `studio-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio`
    - `studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio`
- `tests/`: Comprehensive test suite verifying individual transforms, YAML anchors, line-based description stripping, and DAG numerical fidelity.

## Benchmarks

Run the benchmark suite against an OCIO configuration (defaults to `configs/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio` if no path is passed):

```powershell
python gemini-code-1791882948890.py configs/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio
```
