import pytest

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

ALL_TRANSFORM_CLASSES = [
    (ElideDefaultsTransform, transform_elide_defaults, False),
    (CompactAmfScalarsTransform, transform_compact_amf_scalars, False),
    (FlowTransformsTransform, transform_flow_transforms, False),
    (YamlAnchorsTransform, transform_yaml_anchors, False),
    (StripDescriptionsTransform, transform_strip_descriptions, True),
]


@pytest.mark.parametrize("cls,fn,is_lossy", ALL_TRANSFORM_CLASSES)
def test_transform_protocol_conformance(cls, fn, is_lossy):
    """Every transform class must satisfy the Transform protocol and declare correct metadata."""
    instance = cls()
    assert isinstance(instance, Transform)
    assert isinstance(instance.name, str) and len(instance.name) > 0
    assert isinstance(instance.description, str) and len(instance.description) > 0
    assert instance.is_lossy == is_lossy


@pytest.mark.parametrize("cls,fn,is_lossy", ALL_TRANSFORM_CLASSES)
def test_class_and_function_equivalence(cls, fn, is_lossy, minimal_ocio_yaml):
    """Calling Class().apply(text) must produce identical output to transform_*(text)."""
    instance = cls()
    res_class = instance.apply(minimal_ocio_yaml)
    res_func = fn(minimal_ocio_yaml)
    assert res_class == res_func
