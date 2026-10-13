def test_inlining_builtin_to_scene_reference(ocio_module):
    """Multiline to_scene_reference BuiltinTransform should be flow-inlined."""
    yaml_src = (
        "    to_scene_reference: !<BuiltinTransform>\n"
        "      style: ACEScc_to_ACES2065-1\n"
    )
    result = ocio_module.transform_flow_transforms(yaml_src)
    assert (
        result
        == "    to_scene_reference: !<BuiltinTransform> {style: ACEScc_to_ACES2065-1}\n"
    )


def test_inlining_builtin_from_scene_reference(ocio_module):
    """Multiline from_scene_reference BuiltinTransform should be flow-inlined."""
    yaml_src = (
        "    from_scene_reference: !<BuiltinTransform>\n"
        "      style: ACES2065-1_to_ACEScct\n"
    )
    result = ocio_module.transform_flow_transforms(yaml_src)
    assert (
        result
        == "    from_scene_reference: !<BuiltinTransform> {style: ACES2065-1_to_ACEScct}\n"
    )


def test_inlining_builtin_from_display_reference(ocio_module):
    """Multiline from_display_reference BuiltinTransform should be flow-inlined."""
    yaml_src = (
        "    from_display_reference: !<BuiltinTransform>\n"
        "      style: DISPLAY - CIE-XYZ-D65_to_sRGB\n"
    )
    result = ocio_module.transform_flow_transforms(yaml_src)
    assert (
        result
        == "    from_display_reference: !<BuiltinTransform> {style: DISPLAY - CIE-XYZ-D65_to_sRGB}\n"
    )


def test_inlining_matrix_transform(ocio_module):
    """Multiline MatrixTransform inside transform list should be converted to flow mapping."""
    yaml_src = (
        "      - !<MatrixTransform>\n"
        "        matrix: [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]\n"
    )
    result = ocio_module.transform_flow_transforms(yaml_src)
    expected = "      - !<MatrixTransform> {matrix: [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]}\n"
    assert result == expected


def test_matrix_multiline_whitespace_normalized(ocio_module):
    """Matrix elements wrapped across multiple lines or with extra spaces should be normalized."""
    yaml_src = (
        "      - !<MatrixTransform>\n"
        "        matrix: [ 1.0,  0.0,  0.0, 0.0,\n"
        "                  0.0,  1.0,  0.0, 0.0,\n"
        "                  0.0,  0.0,  1.0, 0.0,\n"
        "                  0.0,  0.0,  0.0, 1.0 ]\n"
    )
    result = ocio_module.transform_flow_transforms(yaml_src)
    assert "\n                  " not in result
    assert result.startswith(
        "      - !<MatrixTransform> {matrix: [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]}\n"
    )


def test_flow_transforms_idempotency(ocio_module):
    """Applying transform_flow_transforms repeatedly should yield identical content."""
    yaml_src = (
        "    to_scene_reference: !<BuiltinTransform>\n"
        "      style: ACEScc_to_ACES2065-1\n"
        "      - !<MatrixTransform>\n"
        "        matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]\n"
    )
    pass1 = ocio_module.transform_flow_transforms(yaml_src)
    pass2 = ocio_module.transform_flow_transforms(pass1)
    assert pass1 == pass2
