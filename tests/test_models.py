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
        parse_time_ms=50.25,
        max_delta=0.0,
        fidelity_passed=True,
        parse_time_mean_ms=51.10,
        parse_time_stddev_ms=1.20,
    )
    assert bench.raw_kb == 80000 / 1024.0
    assert bench.gzip_kb == 10000 / 1024.0
    assert bench.delta_bytes == -20000
    assert "80,000 B" in bench.raw_size_str
    assert "-20,000 B" in bench.delta_str
    assert "51.10 ± 1.20 ms" in bench.timing_str
    assert pytest.approx(bench.reduction_pct, 0.1) == 20.0

    d = bench.to_dict()
    assert d["Name"] == "Elide Defaults"
    assert d["Raw Bytes"] == "80,000 B"
    assert d["Delta Bytes"] == "-20,000 B"
    assert d["Reduction"] == "20.0%"
    assert d["Fidelity"] == "PASS"
    assert d["Parse (ms)"] == "51.10 ± 1.20 ms"
