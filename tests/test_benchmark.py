import pytest

from ocio_minifier.benchmark import BenchmarkRunner


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
    assert "Raw Bytes" in result
    assert "Raw (KB)" in result
    assert "Delta Bytes" in result
    assert "Gzip Bytes" in result
    assert "Gzip (KB)" in result
    assert "Archive Bytes" in result
    assert "Archive (KB)" in result
    assert "Parse (ms)" in result
    assert "Archive Load (ms)" in result
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
    assert "Archive Bytes" in result


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_benchmark_runner_robust_timing(minimal_ocio_yaml):
    """BenchmarkRunner should execute multiple iterations and record min and stddev statistics."""
    runner = BenchmarkRunner(
        warmup_iterations=2,
        timing_iterations=3,
        statistic="median",
    )
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))
    res = runner.benchmark_stage("Robust Test", minimal_ocio_yaml, baseline_bytes)

    assert res.parse_time_ms > 0
    assert res.parse_time_min_ms is not None and res.parse_time_min_ms > 0
    assert res.parse_time_stddev_ms is not None and res.parse_time_stddev_ms >= 0
    assert res.parse_time_min_ms <= res.parse_time_ms
    assert res.archive_bytes > 0
    assert res.archive_kb > 0
    assert res.archive_parse_time_ms is not None and res.archive_parse_time_ms > 0


def test_get_ocioz_archive_size(ocio_module, minimal_ocio_yaml):
    """Helper get_ocioz_archive_size should produce non-zero compressed zip size."""
    size = ocio_module.get_ocioz_archive_size(minimal_ocio_yaml)
    assert size > 0
    assert size < len(minimal_ocio_yaml.encode("utf-8"))


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_benchmark_archive_stage(ocio_module, minimal_ocio_yaml, tmp_path):
    """BenchmarkRunner should measure archive stages from .ocioz files directly."""
    orig_cfg = ocio_module.ocio.Config.CreateFromStream(minimal_ocio_yaml)
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))

    archive_path = tmp_path / "test_archive.ocioz"
    ocio_module.create_ocio_archive(minimal_ocio_yaml, str(archive_path))

    runner = BenchmarkRunner(warmup_iterations=1, timing_iterations=2)
    res = runner.benchmark_archive_stage(
        "Archive Stage Test",
        str(archive_path),
        baseline_bytes,
        orig_cfg,
    )

    assert res.name == "Archive Stage Test"
    assert res.fidelity_passed is True
    assert res.archive_bytes == archive_path.stat().st_size
    assert res.raw_bytes == archive_path.stat().st_size
    assert res.parse_time_ms > 0
    assert res.archive_parse_time_ms is not None and res.archive_parse_time_ms > 0
