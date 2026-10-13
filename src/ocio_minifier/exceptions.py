"""Custom domain exceptions for the OCIO config minifier."""


class OcioMinifierError(Exception):
    """Base exception for all errors raised by the ocio_minifier package."""


class ConfigNotFoundError(OcioMinifierError):
    """Raised when an OCIO configuration file cannot be found."""


class ConfigParsingError(OcioMinifierError):
    """Raised when an OCIO configuration fails schema validation or parsing."""


class FidelityVerificationError(OcioMinifierError):
    """Raised when mathematical DAG fidelity verification fails beyond tolerance."""


class TransformError(OcioMinifierError):
    """Raised when an error occurs while applying a transformation."""
