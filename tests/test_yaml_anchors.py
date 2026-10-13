import pytest


def test_single_occurrence_no_anchor(ocio_module):
    """A matrix appearing only once must not generate an anchor or alias."""
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


def test_multiple_distinct_repeated_matrices(ocio_module):
    """Multiple distinct repeated matrices should generate distinct anchor names (e.g. matrix_ref_0, matrix_ref_1)."""
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


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
def test_anchors_parsed_by_ocio(ocio_module, minimal_ocio_yaml):
    """OCIO parser should resolve anchors and aliases transparently."""
    # Add a repeated matrix colorspace to the minimal config
    repeated_cs = (
        "  - !<ColorSpace>\n"
        "    name: ACEScg_Copy\n"
        "    family: ACES\n"
        "    to_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}\n"
    )
    src = minimal_ocio_yaml + repeated_cs
    transformed = ocio_module.transform_yaml_anchors(src)

    assert "&matrix_ref_0" in transformed
    assert "*matrix_ref_0" in transformed

    # PyOpenColorIO must parse and resolve the alias successfully
    cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
    cfg.validate()
    cs1 = cfg.getColorSpace("ACEScg")
    cs2 = cfg.getColorSpace("ACEScg_Copy")
    assert cs1 is not None and cs2 is not None
