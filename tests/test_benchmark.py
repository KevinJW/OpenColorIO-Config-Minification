import pytest


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_run_benchmark_baseline_entry(ocio_module, minimal_ocio_yaml):
    """Running benchmark for a baseline entry without orig_cfg should succeed with 0% reduction."""
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))
    result = ocio_module.run_benchmark(
        "Baseline", minimal_ocio_yaml, baseline_bytes, orig_cfg=None
    )

    assert result["Name"] == "Baseline"
    assert result["Reduction"] == "0.0%"
    assert result["Fidelity"] == "PASS"
    assert "Raw (KB)" in result
    assert "Gzip (KB)" in result
    assert "Parse (ms)" in result
    assert "Max ΔRGB" in result


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_run_benchmark_reduction_and_fidelity(ocio_module, minimal_ocio_yaml):
    """Running benchmark on a transformed config should measure reduction and verify fidelity."""
    orig_cfg = ocio_module.ocio.Config.CreateFromStream(minimal_ocio_yaml)
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))

    # Apply transform_elide_defaults
    transformed = ocio_module.transform_elide_defaults(minimal_ocio_yaml)
    result = ocio_module.run_benchmark(
        "Elide Defaults", transformed, baseline_bytes, orig_cfg=orig_cfg
    )

    assert result["Name"] == "Elide Defaults"
    assert result["Fidelity"] == "PASS"
    assert float(result["Raw (KB)"]) <= float(result["Raw (KB)"])
    assert result["Max ΔRGB"] == "0.00e+00"
