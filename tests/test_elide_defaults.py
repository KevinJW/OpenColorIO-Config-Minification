import pytest


def test_elide_equalitygroup_empty(ocio_module):
    """Empty equalitygroup quotes should be elided."""
    yaml_src = (
        "colorspaces:\n"
        "  - !<ColorSpace>\n"
        "    name: Test1\n"
        '    equalitygroup: ""\n'
        "  - !<ColorSpace>\n"
        "    name: Test2\n"
        "    equalitygroup: ''\n"
    )
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert 'equalitygroup: ""' not in result
    assert "equalitygroup: ''" not in result
    assert "name: Test1" in result
    assert "name: Test2" in result


def test_preserve_non_empty_equalitygroup(ocio_module):
    """Non-empty equalitygroup values must not be elided."""
    yaml_src = (
        'colorspaces:\n  - !<ColorSpace>\n    name: Test\n    equalitygroup: "aces"\n'
    )
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert 'equalitygroup: "aces"' in result


def test_elide_allocation_uniform(ocio_module):
    """allocation: uniform should be removed, non-uniform preserved."""
    yaml_src = "  allocation: uniform\n  allocation: lg2\n"
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "allocation: uniform" not in result
    assert "allocation: lg2" in result


def test_elide_isdata_false(ocio_module):
    """isdata: false should be removed, isdata: true preserved."""
    yaml_src = "  isdata: false\n  isdata: true\n"
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "isdata: false" not in result
    assert "isdata: true" in result


def test_preserve_bitdepth(ocio_module):
    """bitdepth: 32f, 16f, 8ui must all be preserved (omitting bitdepth changes it to unknown in OCIO)."""
    yaml_src = "  bitdepth: 32f\n  bitdepth: 16f\n  bitdepth: 8ui\n"
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "bitdepth: 32f" in result
    assert "bitdepth: 16f" in result
    assert "bitdepth: 8ui" in result


def test_compact_environment_empty(ocio_module):
    """Multiline empty environment dict should be compacted to single line."""
    yaml_src = "environment:\n  {}\nsearch_path: ''\n"
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "environment: {}" in result
    assert "environment:\n  {}" not in result


def test_preserve_populated_environment(ocio_module):
    """Non-empty environment block must not be altered."""
    yaml_src = "environment:\n  OCIO_ACTIVE_DISPLAYS: sRGB\n"
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "environment:\n  OCIO_ACTIVE_DISPLAYS: sRGB" in result


def test_elide_defaults_idempotent(ocio_module, minimal_ocio_yaml):
    """Applying transform_elide_defaults multiple times must be strictly idempotent."""
    pass1 = ocio_module.transform_elide_defaults(minimal_ocio_yaml)
    pass2 = ocio_module.transform_elide_defaults(pass1)
    assert pass1 == pass2


def test_elide_defaults_crlf_handling(ocio_module):
    """Windows CRLF line endings should be handled correctly without breaking."""
    yaml_src = (
        "colorspaces:\r\n"
        "  - !<ColorSpace>\r\n"
        "    name: Test\r\n"
        "    allocation: uniform\r\n"
        "    isdata: false\r\n"
        "    bitdepth: 32f\r\n"
    )
    result = ocio_module.transform_elide_defaults(yaml_src)
    assert "allocation: uniform" not in result
    assert "isdata: false" not in result
    assert "bitdepth: 32f" in result
    assert "name: Test" in result


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_elide_defaults_valid_ocio(ocio_module, minimal_ocio_yaml):
    """Transformed minimal config must parse and validate in PyOpenColorIO."""
    result = ocio_module.transform_elide_defaults(minimal_ocio_yaml)
    cfg = ocio_module.ocio.Config.CreateFromStream(result)
    cfg.validate()
