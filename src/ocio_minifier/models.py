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

    @property
    def raw_kb(self) -> float:
        return self.raw_bytes / 1024.0

    @property
    def gzip_kb(self) -> float:
        return self.gzip_bytes / 1024.0

    @property
    def reduction_pct(self) -> float:
        if self.baseline_bytes <= 0:
            return 0.0
        delta = ((self.raw_bytes - self.baseline_bytes) / self.baseline_bytes) * 100.0
        return abs(delta) if delta < 0 else 0.0

    def to_dict(self) -> dict[str, str]:
        """Convert metrics to formatted string dictionary matching benchmark table columns."""
        return {
            "Name": self.name,
            "Raw (KB)": f"{self.raw_kb:.2f}",
            "Reduction": f"{self.reduction_pct:.1f}%",
            "Gzip (KB)": f"{self.gzip_kb:.2f}",
            "Parse (ms)": f"{self.parse_time_ms:.2f}",
            "Max ΔRGB": f"{self.max_delta:.2e}",
            "Fidelity": "PASS" if self.fidelity_passed else "FAIL",
        }
