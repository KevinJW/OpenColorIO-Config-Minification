import pytest

from ocio_minifier.benchmark import BenchmarkRunner, format_markdown_table
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.transforms import (
    ElideDefaultsTransform,
    StripDescriptionsTransform,
)
from ocio_minifier.verification import HAS_OCIO, FidelityVerifier


def test_pipeline_composition(minimal_ocio_yaml):
    """Pipeline should execute sequentially and update metadata accurately."""
    pipeline = MinificationPipeline()
    assert len(pipeline) == 0
    assert pipeline.is_lossy is False

    # Identity on empty pipeline
    assert pipeline.run(minimal_ocio_yaml) == minimal_ocio_yaml

    pipeline.add(ElideDefaultsTransform())
    assert len(pipeline) == 1
    assert pipeline.is_lossy is False
    assert "Default Field Elision" in pipeline.transform_names

    pipeline.add(StripDescriptionsTransform())
    assert len(pipeline) == 2
    assert pipeline.is_lossy is True
    assert "Strip Descriptions (Lossy)" in pipeline.transform_names


def test_pipeline_presets():
    """Verify built-in pipeline presets conform to lossless and aggressive contracts."""
    syn = MinificationPipeline.preset_syntactic()
    assert len(syn) == 5
    assert syn.is_lossy is False

    agg = MinificationPipeline.preset_aggressive()
    assert len(agg) == 6
    assert agg.is_lossy is True


@pytest.mark.skipif(not HAS_OCIO, reason="PyOpenColorIO required")
def test_fidelity_verifier_bidirectional(sample_ocio_config, sample_config_text):
    """FidelityVerifier evaluates bidirectional parity and view transforms."""
    verifier = FidelityVerifier(tolerance=1e-6, check_inverse=True)
    import PyOpenColorIO as ocio

    candidate = ocio.Config.CreateFromStream(sample_config_text)
    result = verifier.verify(sample_ocio_config, candidate)

    assert result.passed is True
    assert result.max_delta == 0.0
    assert result.evaluated_spaces > 0
    assert result.evaluated_views > 0
    assert result.failure_count == 0


@pytest.mark.skipif(not HAS_OCIO, reason="PyOpenColorIO required")
def test_benchmark_runner_and_table_formatter(minimal_ocio_yaml):
    """BenchmarkRunner should execute stages and produce markdown tables."""
    runner = BenchmarkRunner()
    results = runner.run_suite(minimal_ocio_yaml)

    assert len(results) == 10
    assert results[0].name.startswith("Baseline")
    assert all(r.fidelity_passed for r in results)

    table = format_markdown_table(results)
    assert "| Transform | Raw Size |" in table
    assert "Baseline (Unmodified)" in table
    assert "Combined (Syntactic Only)" in table
