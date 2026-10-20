import pytest

from ocio_minifier.exceptions import (
    ConfigNotFoundError,
    ConfigParsingError,
    FidelityVerificationError,
    OcioMinifierError,
    TransformError,
)
from ocio_minifier.models import (
    BenchmarkResult,
    ConversionFailure,
    VerificationResult,
)


def test_exception_hierarchy():
    """All custom domain exceptions must inherit from OcioMinifierError."""
    assert issubclass(ConfigNotFoundError, OcioMinifierError)
    assert issubclass(ConfigParsingError, OcioMinifierError)
    assert issubclass(FidelityVerificationError, OcioMinifierError)
    assert issubclass(TransformError, OcioMinifierError)


def test_conversion_failure_str():
    """ConversionFailure should render descriptive diagnostic messages."""
    fail_math = ConversionFailure(
        target_type="ColorSpace",
        identifier="ACEScg",
        input_rgb=(0.18, 0.18, 0.18),
        delta=0.05,
    )
    assert "ACEScg" in str(fail_math)
    assert "0.05" in str(fail_math) or "5.00e-02" in str(fail_math)

    fail_err = ConversionFailure(
        target_type="DisplayView",
        identifier="sRGB/Raw",
        input_rgb=(0.0, 0.0, 0.0),
        error_message="Processor error",
    )
    assert "Error: Processor error" in str(fail_err)


def test_verification_result_properties():
    """VerificationResult properties and conversion methods should return expected values."""
    res = VerificationResult(
        passed=True,
        max_delta=0.0,
        tolerance=1e-6,
        evaluated_spaces=50,
        evaluated_views=10,
    )
    assert res.failure_count == 0
    passed, delta, fails = res.to_tuple()
    assert passed is True
    assert delta == 0.0
    assert len(fails) == 0

    fail = ConversionFailure(
        target_type="ColorSpace",
        identifier="BadSpace",
        input_rgb=(1.0, 1.0, 1.0),
        delta=0.2,
    )
    res_failed = VerificationResult(
        passed=False,
        max_delta=0.2,
        failures=[fail],
    )
    assert res_failed.failure_count == 1
    assert res_failed.passed is False


def test_benchmark_result_metrics():
    """BenchmarkResult metrics and reductions should calculate properly."""
    bench = BenchmarkResult(
        name="Elide Defaults",
        raw_bytes=80000,
        baseline_bytes=100000,
        gzip_bytes=10000,
        archive_bytes=10500,
        parse_time_ms=50.25,
        max_delta=0.0,
        fidelity_passed=True,
        parse_time_mean_ms=51.10,
        parse_time_stddev_ms=1.20,
        archive_parse_time_ms=65.0,
        archive_parse_time_mean_ms=65.5,
        archive_parse_time_stddev_ms=1.5,
    )
    assert bench.raw_kb == 80000 / 1024.0
    assert bench.gzip_kb == 10000 / 1024.0
    assert bench.archive_kb == 10500 / 1024.0
    assert bench.delta_bytes == -20000
    assert "80,000 B" in bench.raw_size_str
    assert "-20,000 B" in bench.delta_str
    assert "10,500 B" in bench.archive_size_str
    assert "51.10 ± 1.20 ms" in bench.timing_str
    assert "65.50 ± 1.50 ms" in bench.archive_timing_str
    assert pytest.approx(bench.reduction_pct, 0.1) == 20.0

    d = bench.to_dict()
    assert d["Name"] == "Elide Defaults"
    assert d["Raw Bytes"] == "80,000 B"
    assert d["Delta Bytes"] == "-20,000 B"
    assert d["Reduction"] == "20.0%"
    assert d["Gzip Bytes"] == "10,000 B"
    assert d["Archive Bytes"] == "10,500 B"
    assert d["Archive (KB)"] == f"{10500 / 1024.0:.2f}"
    assert d["Fidelity"] == "PASS"
    assert d["Parse (ms)"] == "51.10 ± 1.20 ms"
    assert d["Archive Load (ms)"] == "65.50 ± 1.50 ms"


def test_benchmark_result_edge_cases():
    """Test boundary conditions: zero baseline, size increase, and missing stddev."""
    # Zero baseline bytes
    zero_bench = BenchmarkResult(
        name="Zero Baseline",
        raw_bytes=100,
        baseline_bytes=0,
        gzip_bytes=50,
        parse_time_ms=10.0,
        max_delta=0.0,
        fidelity_passed=True,
    )
    assert zero_bench.reduction_pct == 0.0

    # Size expansion (delta > 0) and missing stddev/archive timings
    expanding_bench = BenchmarkResult(
        name="Expansion",
        raw_bytes=120000,
        baseline_bytes=100000,
        gzip_bytes=15000,
        parse_time_ms=25.0,
        max_delta=0.0,
        fidelity_passed=True,
        parse_time_mean_ms=None,
        parse_time_stddev_ms=None,
        archive_parse_time_ms=None,
    )
    assert expanding_bench.delta_bytes == 20000
    assert "+20,000 B (+0.0%)" in expanding_bench.delta_str
    assert expanding_bench.timing_str == "25.00 ms"
    assert expanding_bench.archive_timing_str == "N/A"

    d = expanding_bench.to_dict()
    assert d["Parse (ms)"] == "25.00 ms"
    assert d["Archive Load (ms)"] == "N/A"

    # With archive parse time but without archive stddev
    no_stddev_bench = BenchmarkResult(
        name="No Stddev",
        raw_bytes=100,
        baseline_bytes=100,
        gzip_bytes=50,
        parse_time_ms=10.0,
        max_delta=0.0,
        fidelity_passed=True,
        archive_parse_time_ms=15.0,
        archive_parse_time_stddev_ms=None,
    )
    assert no_stddev_bench.archive_timing_str == "15.00 ms"
