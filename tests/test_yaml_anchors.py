def test_single_occurrence_no_anchor(ocio_module):
    """A transform appearing only once must not generate an anchor or alias."""
    yaml_src = "transform: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}\n"
    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&matrix_ref" not in result
    assert "*matrix_ref" not in result
    assert result == yaml_src


def test_repeated_matrix_anchor_and_alias(ocio_module):
    """A repeated matrix should produce an anchor on the first instance and alias on subsequent instances."""
    mat_str = (
        "!<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}"
    )
    yaml_src = f"first: {mat_str}\nsecond: {mat_str}\nthird: {mat_str}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&matrix_ref_0 " + mat_str in result
    assert "*matrix_ref_0" in result
    assert result.count("&matrix_ref_0") == 1
    assert result.count("*matrix_ref_0") == 2


def test_repeated_builtin_transforms(ocio_module):
    """Repeated BuiltinTransforms should generate builtin_ref anchors and aliases."""
    builtin_str = "!<BuiltinTransform> {style: ACEScc_to_ACES2065-1}"
    yaml_src = f"cs1: {builtin_str}\ncs2: {builtin_str}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&builtin_ref_0 " + builtin_str in result
    assert "*builtin_ref_0" in result


def test_repeated_view_mappings(ocio_module):
    """Repeated View mappings should generate view_ref anchors and aliases."""
    view_str = "!<View> {name: Raw, colorspace: Raw}"
    yaml_src = f"sRGB:\n  - {view_str}\nDisplay P3:\n  - {view_str}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert f"&view_ref_0 {view_str}" in result
    assert "*view_ref_0" in result


def test_repeated_exponent_and_logcam_transforms(ocio_module):
    """Repeated Exponent and LogCamera transforms should generate respective namespace anchors."""
    exp_str = "!<ExponentTransform> {value: [2.2, 2.2, 2.2, 1.0]}"
    logcam_str = "!<LogCameraTransform> {base: 2, lin_side_slope: 1.0}"
    yaml_src = f"e1: {exp_str}\ne2: {exp_str}\nl1: {logcam_str}\nl2: {logcam_str}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&exponent_ref_0" in result
    assert "*exponent_ref_0" in result
    assert "&logcam_ref_0" in result
    assert "*logcam_ref_0" in result


def test_multiple_distinct_repeated_matrices(ocio_module):
    """Multiple distinct repeated matrices should generate distinct anchor names."""
    mat_a = (
        "!<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}"
    )
    mat_b = (
        "!<MatrixTransform> {matrix: [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1]}"
    )
    yaml_src = f"a1: {mat_a}\nb1: {mat_b}\na2: {mat_a}\nb2: {mat_b}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&matrix_ref_0" in result
    assert "*matrix_ref_0" in result
    assert "&matrix_ref_1" in result
    assert "*matrix_ref_1" in result


def test_scientific_notation_in_matrix(ocio_module):
    """Matrix values containing scientific notation should be recognized and anchored correctly."""
    mat_str = "!<MatrixTransform> {matrix: [1.0e-05, 0.0, 0.0, 0.0, 0.0, 1.0e-05, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]}"
    yaml_src = f"t1: {mat_str}\nt2: {mat_str}\n"

    result = ocio_module.transform_yaml_anchors(yaml_src)
    assert "&matrix_ref_0" in result
    assert "*matrix_ref_0" in result


def test_mixed_anchors_parsed_by_ocio(ocio_module, minimal_ocio_yaml):
    """OCIO parser should resolve anchors and aliases across matrix and builtin types."""
    # Add repeated colorspaces and views
    extra_yaml = (
        "  - !<ColorSpace>\n"
        "    name: ACEScg_Copy\n"
        "    family: ACES\n"
        "    to_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}\n"
        "  - !<ColorSpace>\n"
        "    name: Builtin1\n"
        "    to_scene_reference: !<BuiltinTransform> {style: ACEScc_to_ACES2065-1}\n"
        "  - !<ColorSpace>\n"
        "    name: Builtin2\n"
        "    to_scene_reference: !<BuiltinTransform> {style: ACEScc_to_ACES2065-1}\n"
    )
    src = minimal_ocio_yaml + extra_yaml
    transformed = ocio_module.transform_yaml_anchors(src)

    assert "&matrix_ref_0" in transformed
    assert "*matrix_ref_0" in transformed
    assert "&builtin_ref_0" in transformed
    assert "*builtin_ref_0" in transformed

    # PyOpenColorIO must parse and resolve all aliases successfully
    cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
    cfg.validate()
    assert cfg.getColorSpace("ACEScg") is not None
    assert cfg.getColorSpace("ACEScg_Copy") is not None
    assert cfg.getColorSpace("Builtin1") is not None
    assert cfg.getColorSpace("Builtin2") is not None
