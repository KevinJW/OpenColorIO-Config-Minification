"""Data models and value objects for the OCIO minification package."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversionFailure:
    """Represents a single mathematical or processing failure during DAG fidelity verification."""

    target_type: str
    identifier: str
    input_rgb: tuple[float, float, float]
    delta: float = 0.0
    error_message: str | None = None

    def __str__(self) -> str:
        if self.error_message:
            return (
                f"{self.target_type} '{self.identifier}' [Error: {self.error_message}]"
            )
        return f"{self.target_type} '{self.identifier}' [In: {list(self.input_rgb)}] (Δ: {self.delta:.2e})"


@dataclass
class VerificationResult:
    """Outcome of evaluating mathematical DAG fidelity across all ColorSpaces and Views."""

    passed: bool
    max_delta: float
    tolerance: float = 1e-6
    evaluated_spaces: int = 0
    evaluated_views: int = 0
    failures: list[ConversionFailure] = field(default_factory=list)
    serialized_diff: str | None = None

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    def to_tuple(self) -> tuple[bool, float, list[str]]:
        """Return backward-compatible (passed, max_delta, failed_conversions) tuple."""
        return self.passed, self.max_delta, [str(f) for f in self.failures]


@dataclass
class BenchmarkResult:
    """Metrics and fidelity results for a single transformation stage."""

    name: str
    raw_bytes: int
    baseline_bytes: int
    gzip_bytes: int
    parse_time_ms: float
    max_delta: float
    fidelity_passed: bool
    archive_bytes: int = 0
    parse_time_min_ms: float | None = None
    parse_time_max_ms: float | None = None
    parse_time_mean_ms: float | None = None
    parse_time_stddev_ms: float | None = None
    archive_parse_time_ms: float | None = None
    archive_parse_time_min_ms: float | None = None
    archive_parse_time_max_ms: float | None = None
    archive_parse_time_mean_ms: float | None = None
    archive_parse_time_stddev_ms: float | None = None

    @property
    def raw_kb(self) -> float:
        return self.raw_bytes / 1024.0

    @property
    def gzip_kb(self) -> float:
        return self.gzip_bytes / 1024.0

    @property
    def archive_kb(self) -> float:
        return self.archive_bytes / 1024.0

    @property
    def delta_bytes(self) -> int:
        return self.raw_bytes - self.baseline_bytes

    @property
    def reduction_pct(self) -> float:
        if self.baseline_bytes <= 0:
            return 0.0
        delta = ((self.raw_bytes - self.baseline_bytes) / self.baseline_bytes) * 100.0
        return abs(delta) if delta < 0 else 0.0

    @property
    def raw_size_str(self) -> str:
        return f"{self.raw_bytes:,} B ({self.raw_kb:.2f} KB)"

    @property
    def gzip_size_str(self) -> str:
        return f"{self.gzip_bytes:,} B ({self.gzip_kb:.2f} KB)"

    @property
    def archive_size_str(self) -> str:
        return f"{self.archive_bytes:,} B ({self.archive_kb:.2f} KB)"

    @property
    def delta_str(self) -> str:
        if self.delta_bytes == 0:
            return "0 B (0.0%)"
        if self.delta_bytes < 0:
            return f"{self.delta_bytes:,} B (-{self.reduction_pct:.1f}%)"
        return f"+{self.delta_bytes:,} B (+0.0%)"

    @property
    def timing_str(self) -> str:
        mean_val = (
            self.parse_time_mean_ms
            if self.parse_time_mean_ms is not None
            else self.parse_time_ms
        )
        if self.parse_time_stddev_ms is not None:
            return f"{mean_val:.2f} ± {self.parse_time_stddev_ms:.2f} ms"
        return f"{self.parse_time_ms:.2f} ms"

    @property
    def archive_timing_str(self) -> str:
        if self.archive_parse_time_ms is None:
            return "N/A"
        mean_val = (
            self.archive_parse_time_mean_ms
            if self.archive_parse_time_mean_ms is not None
            else self.archive_parse_time_ms
        )
        if self.archive_parse_time_stddev_ms is not None:
            return f"{mean_val:.2f} ± {self.archive_parse_time_stddev_ms:.2f} ms"
        return f"{self.archive_parse_time_ms:.2f} ms"

    def to_dict(self) -> dict[str, str]:
        """Convert metrics to formatted string dictionary matching benchmark table columns."""
        mean_val = (
            self.parse_time_mean_ms
            if self.parse_time_mean_ms is not None
            else self.parse_time_ms
        )
        if self.parse_time_stddev_ms is not None and self.parse_time_stddev_ms > 0:
            parse_str = f"{mean_val:.2f} ± {self.parse_time_stddev_ms:.2f} ms"
        else:
            parse_str = f"{self.parse_time_ms:.2f} ms"

        delta_str = f"{self.delta_bytes:+,} B" if self.delta_bytes != 0 else "0 B"

        return {
            "Name": self.name,
            "Raw Bytes": f"{self.raw_bytes:,} B",
            "Raw (KB)": f"{self.raw_kb:.2f}",
            "Delta Bytes": delta_str,
            "Reduction": f"{self.reduction_pct:.1f}%",
            "Gzip Bytes": f"{self.gzip_bytes:,} B",
            "Gzip (KB)": f"{self.gzip_kb:.2f}",
            "Archive Bytes": f"{self.archive_bytes:,} B",
            "Archive (KB)": f"{self.archive_kb:.2f}",
            "Parse (ms)": parse_str,
            "Archive Load (ms)": self.archive_timing_str,
            "Max ΔRGB": f"{self.max_delta:.2e}",
            "Fidelity": "PASS" if self.fidelity_passed else "FAIL",
        }
