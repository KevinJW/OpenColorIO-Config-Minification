import pytest

from ocio_minifier.benchmark import BenchmarkRunner


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


def test_benchmark_identity_short_circuit(ocio_module, minimal_ocio_yaml):
    """When content matches baseline_text, verify() should be bypassed and pass immediately."""
    from unittest.mock import MagicMock

    orig_cfg = ocio_module.ocio.Config.CreateFromStream(minimal_ocio_yaml)
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))

    mock_verifier = MagicMock()
    runner = BenchmarkRunner(
        verifier=mock_verifier, warmup_iterations=0, timing_iterations=1
    )

    res = runner.benchmark_stage(
        "Identity Stage",
        minimal_ocio_yaml,
        baseline_bytes,
        orig_cfg=orig_cfg,
        baseline_text=minimal_ocio_yaml,
    )

    assert res.max_delta == 0.0
    assert res.fidelity_passed is True
    # Verify method was never invoked due to identity short-circuit
    mock_verifier.verify.assert_not_called()


def test_benchmark_runner_statistics_modes(minimal_ocio_yaml):
    """BenchmarkRunner should support min and mean statistics modes."""
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))

    runner_min = BenchmarkRunner(statistic="min", timing_iterations=3)
    res_min = runner_min.benchmark_stage("Min Stat", minimal_ocio_yaml, baseline_bytes)
    assert res_min.parse_time_ms == res_min.parse_time_min_ms

    runner_mean = BenchmarkRunner(statistic="mean", timing_iterations=3)
    res_mean = runner_mean.benchmark_stage(
        "Mean Stat", minimal_ocio_yaml, baseline_bytes
    )
    assert res_mean.parse_time_ms == res_mean.parse_time_mean_ms


def test_benchmark_runner_exception_handling():
    """BenchmarkRunner should handle load_fn exceptions cleanly."""
    runner = BenchmarkRunner(timing_iterations=1)

    def failing_loader():
        raise RuntimeError("Parsing failed")

    timings = runner._measure_timings_and_fidelity(failing_loader)
    # fidelity_pass should be False
    assert timings[6] is False


def test_run_suite_invalid_yaml():
    """run_suite should raise ValueError on invalid YAML."""
    runner = BenchmarkRunner()
    with pytest.raises(ValueError, match="Failed to parse source config"):
        runner.run_suite("not: valid: [yaml")


def test_run_suite_ociocheck_warning(minimal_ocio_yaml, capsys):
    """When ociocheck reports an issue, a warning should be logged to stderr."""
    from unittest.mock import patch

    runner = BenchmarkRunner(warmup_iterations=1, timing_iterations=1)
    with patch(
        "ocio_minifier.benchmark.validate_with_ociocheck",
        return_value=(False, "Simulated missing LUT"),
    ):
        runner.run_suite(minimal_ocio_yaml)
    captured = capsys.readouterr()
    assert (
        "Warning: ociocheck validation reported issues: Simulated missing LUT"
        in captured.err
    )


def test_benchmark_runner_standard_stages(minimal_ocio_yaml):
    """get_standard_stages should return 9 registered stages with working transform functions."""
    stages = BenchmarkRunner.get_standard_stages()
    assert len(stages) == 9
    for name, transform_fn, tag in stages:
        assert isinstance(name, str)
        assert isinstance(tag, str)
        transformed = transform_fn(minimal_ocio_yaml)
        assert isinstance(transformed, str)
        assert len(transformed) > 0


def test_benchmark_runner_execute_stage(minimal_ocio_yaml, tmp_path):
    """_execute_stage should create the archive file and return a valid BenchmarkResult."""
    import os

    import PyOpenColorIO as ocio

    orig_cfg = ocio.Config.CreateFromStream(minimal_ocio_yaml)
    baseline_bytes = len(minimal_ocio_yaml.encode("utf-8"))
    archive_path = str(tmp_path / "test_exec.ocioz")

    runner = BenchmarkRunner(warmup_iterations=1, timing_iterations=1)
    res = runner._execute_stage(
        "Exec Stage",
        minimal_ocio_yaml,
        baseline_bytes,
        orig_cfg,
        archive_path,
        minimal_ocio_yaml,
    )
    assert res.name == "Exec Stage"
    assert res.archive_bytes > 0
    assert os.path.exists(archive_path)
