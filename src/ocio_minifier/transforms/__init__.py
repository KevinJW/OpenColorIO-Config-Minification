"""Minification transformations and protocol."""

from ocio_minifier.transforms.amf import (
    CompactAmfScalarsTransform,
    transform_compact_amf_scalars,
)
from ocio_minifier.transforms.base import Transform
from ocio_minifier.transforms.cdl import (
    FlowCdlTransformsTransform,
    transform_flow_cdl_transforms,
)
from ocio_minifier.transforms.defaults import (
    ElideDefaultsTransform,
    transform_elide_defaults,
)
from ocio_minifier.transforms.descriptions import (
    StripDescriptionsTransform,
    transform_strip_descriptions,
)
from ocio_minifier.transforms.flow import (
    FlowTransformsTransform,
    transform_flow_transforms,
)
from ocio_minifier.transforms.precision import (
    FloatPrecisionTransform,
    transform_float_precision,
)
from ocio_minifier.transforms.yaml_anchors import (
    YamlAnchorsTransform,
    transform_yaml_anchors,
)

__all__ = [
    "CompactAmfScalarsTransform",
    "ElideDefaultsTransform",
    "FloatPrecisionTransform",
    "FlowCdlTransformsTransform",
    "FlowTransformsTransform",
    "StripDescriptionsTransform",
    "Transform",
    "YamlAnchorsTransform",
    "transform_compact_amf_scalars",
    "transform_elide_defaults",
    "transform_float_precision",
    "transform_flow_cdl_transforms",
    "transform_flow_transforms",
    "transform_strip_descriptions",
    "transform_yaml_anchors",
]
