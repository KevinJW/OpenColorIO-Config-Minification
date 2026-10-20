from pathlib import Path

import pytest

from ocio_minifier.cli import main
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.transforms.amf import transform_compact_amf_scalars
from ocio_minifier.transforms.cdl import transform_flow_cdl_transforms
from ocio_minifier.transforms.defaults import transform_elide_defaults
from ocio_minifier.transforms.descriptions import transform_strip_descriptions
from ocio_minifier.transforms.flow import transform_flow_transforms
from ocio_minifier.transforms.precision import transform_float_precision
from ocio_minifier.transforms.yaml_anchors import transform_yaml_anchors
from ocio_minifier.verification import (
    FidelityVerifier,
    diff_serialized_configs,
    ocio,
)


def test_diff_serialized_identical_configs(minimal_ocio_yaml):
    """Diffing serialized representations of identical configs must produce an empty string."""
    cfg1 = ocio.Config.CreateFromStream(minimal_ocio_yaml)
    cfg2 = ocio.Config.CreateFromStream(minimal_ocio_yaml)

    diff = diff_serialized_configs(cfg1, cfg2)
    assert diff == ""


def test_diff_serialized_lossless_transforms_produce_zero_diff(sample_config_text):
    """Lossless transforms and full syntactic pipeline must yield 100% identical serialized OCIO profiles."""
    orig_cfg = ocio.Config.CreateFromStream(sample_config_text)

    # Test Default Field Elision
    elide_text = transform_elide_defaults(sample_config_text)
    elide_cfg = ocio.Config.CreateFromStream(elide_text)
    assert diff_serialized_configs(orig_cfg, elide_cfg) == ""

    # Test YAML Anchors
    anchored_text = transform_yaml_anchors(sample_config_text)
    anchored_cfg = ocio.Config.CreateFromStream(anchored_text)
    assert diff_serialized_configs(orig_cfg, anchored_cfg) == ""

    # Test Compact AMF
    amf_text = transform_compact_amf_scalars(sample_config_text)
    amf_cfg = ocio.Config.CreateFromStream(amf_text)
    assert diff_serialized_configs(orig_cfg, amf_cfg) == ""

    # Test Flow Transforms
    flow_text = transform_flow_transforms(sample_config_text)
    flow_cfg = ocio.Config.CreateFromStream(flow_text)
    assert diff_serialized_configs(orig_cfg, flow_cfg) == ""

    # Test CDL Flow
    cdl_text = transform_flow_cdl_transforms(sample_config_text)
    cdl_cfg = ocio.Config.CreateFromStream(cdl_text)
    assert diff_serialized_configs(orig_cfg, cdl_cfg) == ""

    # Test Entire Lossless Syntactic Pipeline
    pipeline = MinificationPipeline.preset_syntactic()
    syntactic_min = pipeline.run(sample_config_text)
    syntactic_cfg = ocio.Config.CreateFromStream(syntactic_min)
    assert diff_serialized_configs(orig_cfg, syntactic_cfg) == ""


def test_diff_serialized_lossy_transforms_show_targeted_diffs(sample_config_text):
    """Lossy transforms (description strip, precision) must show precise semantic diffs."""
    orig_cfg = ocio.Config.CreateFromStream(sample_config_text)

    # Strip descriptions: diff must reflect removed description text
    desc_text = transform_strip_descriptions(sample_config_text)
    desc_cfg = ocio.Config.CreateFromStream(desc_text)
    desc_diff = diff_serialized_configs(orig_cfg, desc_cfg)
    assert "-description:" in desc_diff or "-    description:" in desc_diff

    # Float precision rounding: diff must reflect modified numbers
    prec_text = transform_float_precision(sample_config_text, decimals=3)
    prec_cfg = ocio.Config.CreateFromStream(prec_text)
    prec_diff = diff_serialized_configs(orig_cfg, prec_cfg)
    assert len(prec_diff) > 0
    assert "--- original_serialized.ocio" in prec_diff


def test_fidelity_verifier_with_serialized_diff(minimal_ocio_yaml):
    """FidelityVerifier with include_serialized_diff=True should populate serialized_diff field."""
    orig_cfg = ocio.Config.CreateFromStream(minimal_ocio_yaml)
    cand_cfg = ocio.Config.CreateFromStream(minimal_ocio_yaml)

    verifier = FidelityVerifier(include_serialized_diff=True)
    res = verifier.verify(orig_cfg, cand_cfg)
    assert res.passed is True
    assert res.serialized_diff == ""


def test_cli_diff_option(capsys):
    """CLI --diff option should print serialized unified diff."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    # Run with aggressive preset to ensure a non-empty diff
    ret = main([str(source_file), "--preset", "aggressive", "--diff"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "--- original_serialized.ocio" in captured.out
    assert "+++ minified_serialized.ocio" in captured.out
