"""OpenColorIO Config Minification and Verification Toolkit."""

from ocio_minifier.benchmark import (
    BenchmarkRunner,
    format_markdown_table,
    run_benchmark,
)
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
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.transforms import (
    CompactAmfScalarsTransform,
    ElideDefaultsTransform,
    FloatPrecisionTransform,
    FlowCdlTransformsTransform,
    FlowTransformsTransform,
    StripDescriptionsTransform,
    Transform,
    YamlAnchorsTransform,
    transform_compact_amf_scalars,
    transform_elide_defaults,
    transform_float_precision,
    transform_flow_cdl_transforms,
    transform_flow_transforms,
    transform_strip_descriptions,
    transform_yaml_anchors,
)
from ocio_minifier.verification import (
    DEFAULT_PIXEL_GRID,
    HAS_OCIO,
    FidelityVerifier,
    ocio,
    verify_dag_fidelity,
)

__version__ = "0.1.0"
__all__ = [
    "DEFAULT_PIXEL_GRID",
    "HAS_OCIO",
    "BenchmarkResult",
    "BenchmarkRunner",
    "CompactAmfScalarsTransform",
    "ConfigNotFoundError",
    "ConfigParsingError",
    "ConversionFailure",
    "ElideDefaultsTransform",
    "FidelityVerificationError",
    "FidelityVerifier",
    "FloatPrecisionTransform",
    "FlowCdlTransformsTransform",
    "FlowTransformsTransform",
    "MinificationPipeline",
    "OcioMinifierError",
    "StripDescriptionsTransform",
    "Transform",
    "TransformError",
    "VerificationResult",
    "YamlAnchorsTransform",
    "__version__",
    "format_markdown_table",
    "ocio",
    "run_benchmark",
    "transform_compact_amf_scalars",
    "transform_elide_defaults",
    "transform_float_precision",
    "transform_flow_cdl_transforms",
    "transform_flow_transforms",
    "transform_strip_descriptions",
    "transform_yaml_anchors",
    "verify_dag_fidelity",
]
