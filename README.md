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

Install the package and development dependencies using pip:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .[dev]
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

- **Markdown Linting (markdownlint)**: Validates Markdown style, headings, and structure.

  ```powershell
  pre-commit run markdownlint --all-files
  ```

## Usage

### Command-Line Interface (`ocio-minify`)

Minify an OCIO configuration with lossless syntactic compression and mathematical verification:

```powershell
ocio-minify configs/cg-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio -o minified.ocio --verify
```

Use aggressive compression (lossless syntactic transforms + description stripping):

```powershell
ocio-minify configs/studio-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio -o studio-min.ocio --preset aggressive --verify
```

Run the benchmark suite comparing all transforms with DAG fidelity checks:

```powershell
# Markdown table (default)
ocio-minify configs/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio --benchmark

# JSON output (for automated CI/CD metric tracking)
ocio-minify configs/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio --benchmark --format json

# Re-serialize original and minified configs via PyOpenColorIO and display unified diff
ocio-minify configs/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio --preset aggressive --diff
```

### Python API

```python
from ocio_minifier import (
    MinificationPipeline,
    FidelityVerifier,
    diff_serialized_configs,
)

# Run lossless syntactic minification
pipeline = MinificationPipeline.preset_syntactic()
minified_text = pipeline.run(raw_ocio_yaml)

# Run aggressive lossy minification
aggressive_pipeline = MinificationPipeline.preset_aggressive(precision=7)
compact_text = aggressive_pipeline.run(raw_ocio_yaml)

# Validate exact canonical serialization diff
diff_output = diff_serialized_configs(orig_cfg, cand_cfg)
```

## Project Structure

- `src/ocio_minifier/`: Modular package source:
  - `transforms/`: Individual transform implementations conforming to `Transform` protocol.
  - `pipeline.py`: Composable `MinificationPipeline` and preset definitions.
  - `verification.py`: `FidelityVerifier` testing forward, inverse, and display/view mathematical parity.
  - `benchmark.py`: `BenchmarkRunner` measuring size reductions, parse time, and fidelity.
  - `cli.py`: Production `argparse` CLI implementation.
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
- `tests/`: Comprehensive test suite verifying individual transforms, YAML anchors, line-based description stripping, models, and DAG numerical fidelity.
