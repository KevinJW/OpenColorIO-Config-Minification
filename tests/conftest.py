import importlib
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"
SAMPLE_CONFIG_PATH = (
    CONFIGS_DIR / "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio"
)


@pytest.fixture(scope="session")
def ocio_module():
    """Import and return the core minification module."""
    return importlib.import_module("ocio_minifier")


@pytest.fixture(scope="session")
def sample_config_text():
    """Load the full studio sample OCIO configuration file as text."""
    if not SAMPLE_CONFIG_PATH.exists():
        pytest.skip(f"Sample config file {SAMPLE_CONFIG_PATH} not found")
    return SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sample_ocio_config(ocio_module, sample_config_text):
    """Parse and validate the studio sample OCIO configuration object."""
    if not ocio_module.HAS_OCIO:
        pytest.skip("PyOpenColorIO is not available in environment")
    cfg = ocio_module.ocio.Config.CreateFromStream(sample_config_text)
    cfg.validate()
    return cfg


@pytest.fixture
def minimal_ocio_yaml():
    """Return a minimal syntactically valid OCIO v2 configuration YAML text."""
    return """ocio_profile_version: 2.0

environment:
  {}

search_path: ""
strictparsing: true
luma: [0.2126, 0.7152, 0.0722]

roles:
  default: Raw
  scene_linear: ACEScg

file_rules:
  - !<Rule> {name: Default, colorspace: Raw}

displays:
  sRGB:
    - !<View> {name: Raw, colorspace: Raw}

colorspaces:
  - !<ColorSpace>
    name: Raw
    family: Raw
    equalitygroup: ""
    bitdepth: 32f
    isdata: true
    allocation: uniform

  - !<ColorSpace>
    name: ACEScg
    family: ACES
    equalitygroup: ""
    bitdepth: 32f
    isdata: false
    allocation: uniform
    to_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
"""
