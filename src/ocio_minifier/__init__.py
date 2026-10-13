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
from ocio_minifier.transforms import (
    CompactAmfScalarsTransform,
    ElideDefaultsTransform,
    FlowTransformsTransform,
    StripDescriptionsTransform,
    Transform,
    YamlAnchorsTransform,
    transform_compact_amf_scalars,
    transform_elide_defaults,
    transform_flow_transforms,
    transform_strip_descriptions,
    transform_yaml_anchors,
)

__version__ = "0.1.0"
__all__ = [
    "BenchmarkResult",
    "CompactAmfScalarsTransform",
    "ConfigNotFoundError",
    "ConfigParsingError",
    "ConversionFailure",
    "ElideDefaultsTransform",
    "FidelityVerificationError",
    "FlowTransformsTransform",
    "OcioMinifierError",
    "StripDescriptionsTransform",
    "Transform",
    "TransformError",
    "VerificationResult",
    "YamlAnchorsTransform",
    "__version__",
    "transform_compact_amf_scalars",
    "transform_elide_defaults",
    "transform_flow_transforms",
    "transform_strip_descriptions",
    "transform_yaml_anchors",
]
