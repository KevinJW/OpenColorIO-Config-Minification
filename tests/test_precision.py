from ocio_minifier.transforms.precision import (
    transform_float_precision,
)


def test_float_precision_rounding_basic():
    """Basic float precision rounding for 4x4 matrices."""
    yaml_src = (
        "      matrix: [0.9999999999999999, 1.0000000000000002, 0.0, 0.0, "
        "0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]\n"
    )
    res = transform_float_precision(yaml_src, decimals=6)
    assert "matrix: [1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]" in res


def test_float_precision_preserves_row_sum_unity():
    """Matrix row summing to 1.0 must maintain exact 1.0 sum after precision reduction."""
    # Row 0: 0.6954907 + 0.2410786 + 0.0634307 = 1.0000000
    # Naive rounding to 3 decimals: 0.695 + 0.241 + 0.063 = 0.999 (broken)
    # Invariant preservation allocates +0.001 to 0.695 -> 0.696, sum = 1.000
    row0 = [0.6954907, 0.2410786, 0.0634307, 0.0]
    row1 = [0.0, 1.0, 0.0, 0.0]
    row2 = [0.0, 0.0, 1.0, 0.0]
    row3 = [0.0, 0.0, 0.0, 1.0]
    matrix_16 = row0 + row1 + row2 + row3

    yaml_src = f"      matrix: [{', '.join(str(x) for x in matrix_16)}]\n"

    # With invariant preservation
    res_preserved = transform_float_precision(
        yaml_src, decimals=3, preserve_matrix_row_sums=True
    )
    assert "0.696, 0.241, 0.063" in res_preserved

    # Without invariant preservation
    res_unpreserved = transform_float_precision(
        yaml_src, decimals=3, preserve_matrix_row_sums=False
    )
    assert "0.695, 0.241, 0.063" in res_unpreserved


def test_float_precision_preserves_row_sum_zero():
    """Opponent/chrominance row summing to 0.0 must maintain exact 0.0 sum after precision reduction."""
    # Row: 0.2104 + (-0.1502) + (-0.0602) = 0.0000
    row0 = [0.2104, -0.1502, -0.0602, 0.0]
    row1 = [0.0, 1.0, 0.0, 0.0]
    row2 = [0.0, 0.0, 1.0, 0.0]
    row3 = [0.0, 0.0, 0.0, 1.0]
    matrix_16 = row0 + row1 + row2 + row3

    yaml_src = f"      matrix: [{', '.join(str(x) for x in matrix_16)}]\n"
    res = transform_float_precision(yaml_src, decimals=2, preserve_matrix_row_sums=True)

    # In 2 decimals: 0.21 - 0.15 - 0.06 = 0.0
    assert "0.21, -0.15, -0.06" in res


def test_float_precision_snaps_affine_row_and_offsets():
    """Near-zero translation offsets and affine bottom row should snap to exact 0 and [0,0,0,1]."""
    matrix_16 = [
        1.0,
        0.0,
        0.0,
        1e-9,
        0.0,
        1.0,
        0.0,
        -1e-9,
        0.0,
        0.0,
        1.0,
        0.0,
        1e-8,
        -1e-8,
        1e-9,
        1.00000001,
    ]
    yaml_src = f"      matrix: [{', '.join(str(x) for x in matrix_16)}]\n"
    res = transform_float_precision(yaml_src, decimals=6)
    assert "[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]" in res


def test_float_precision_preserves_cdl_channel_symmetry():
    """CDL 3-vectors with virtually identical channels should maintain exact cross-channel equality."""
    yaml_src = "    slope: [1.10004, 1.09996, 1.10000]\n"
    res_sym = transform_float_precision(
        yaml_src, decimals=3, preserve_channel_symmetry=True
    )
    assert "slope: [1.1, 1.1, 1.1]" in res_sym

    res_asym = transform_float_precision(
        yaml_src, decimals=5, preserve_channel_symmetry=False
    )
    assert res_asym != "    slope: [1.1, 1.1, 1.1]\n"
    assert "1.10004" in res_asym


def test_float_precision_invalid_float():
    """Non-numeric tokens in array must be safely preserved."""
    yaml_src = "      matrix: [invalid, 1.0]\n"
    res = transform_float_precision(yaml_src, decimals=6)
    assert "matrix: [invalid, 1]" in res


def test_float_precision_tiny_float_and_generic_vector():
    """Tiny floats (<1e-4) format in scientific notation, and generic vector lengths are rounded."""
    yaml_src = "    power: [0.0000123456, 1.2345678, 2.3456789, 3.4567890]\n"
    res = transform_float_precision(yaml_src, decimals=6)
    assert "1.2e-05" in res or "1.2e-5" in res
    assert "1.234568" in res
