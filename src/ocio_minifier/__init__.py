"""OpenColorIO Config Minification and Verification Toolkit."""

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

__version__ = "0.1.0"
__all__ = [
    "BenchmarkResult",
    "ConfigNotFoundError",
    "ConfigParsingError",
    "ConversionFailure",
    "FidelityVerificationError",
    "OcioMinifierError",
    "TransformError",
    "VerificationResult",
    "__version__",
]
