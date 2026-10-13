import os

import pytest

try:
    import PyOpenColorIO as ocio

    HAS_OCIO = True
except ImportError:
    HAS_OCIO = False


def test_ocio_available():
    """Verify PyOpenColorIO is installed and importable."""
    assert HAS_OCIO is True
    assert hasattr(ocio, "__version__")
    assert ocio.__version__ is not None


ALL_CONFIG_FILES = [
    "cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio",
    "cg-config-v2.1.0_aces-v1.3_ocio-v2.3.ocio",
    "cg-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
    "cg-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
    "cg-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio",
    "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
    "studio-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio",
    "studio-config-v2.1.0_aces-v1.3_ocio-v2.3.ocio",
    "studio-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
    "studio-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
    "studio-config-v5.0.0_aces-v2.1_ocio-v2.6.ocio",
]


@pytest.mark.skipif(not HAS_OCIO, reason="PyOpenColorIO not available")
def test_load_sample_config():
    """Verify the sample studio OCIO configuration parses and validates cleanly."""
    sample_file = os.path.join(
        "configs", "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio"
    )
    assert os.path.exists(sample_file), f"File {sample_file} not found"

    cfg = ocio.Config.CreateFromFile(sample_file)
    cfg.validate()

    # Check key color spaces
    cs_names = [cs.getName() for cs in cfg.getColorSpaces()]
    assert len(cs_names) > 0
    assert (
        "ACES2065-1" in cs_names
        or cfg.getColorSpace(ocio.ROLE_SCENE_LINEAR) is not None
    )


@pytest.mark.skipif(not HAS_OCIO, reason="PyOpenColorIO not available")
@pytest.mark.parametrize("config_filename", ALL_CONFIG_FILES)
def test_load_all_builtin_configs(config_filename):
    """Verify every configuration in configs/ parses and validates cleanly with PyOpenColorIO."""
    config_path = os.path.join("configs", config_filename)
    assert os.path.exists(config_path), f"Configuration file {config_path} not found"

    cfg = ocio.Config.CreateFromFile(config_path)
    cfg.validate()

    # Assert basic validity and non-empty color spaces
    cs_list = list(cfg.getColorSpaces())
    assert len(cs_list) > 0
