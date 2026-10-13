from ocio_minifier.transforms.precision import transform_float_precision


def test_float_precision_rounding():
    yaml_src = (
        "      matrix: [0.9999999999999999, 1.0000000000000002, 0.0, -0.0000000123]\n"
    )
    res = transform_float_precision(yaml_src, decimals=6)
    assert "matrix: [1, 1, 0, 0]" in res


def test_float_precision_preserves_integers():
    yaml_src = "      matrix: [1, 0, 0, 1.0, -1.0]\n"
    res = transform_float_precision(yaml_src, decimals=6)
    assert "matrix: [1, 0, 0, 1, -1]" in res


def test_float_precision_invalid_float():
    yaml_src = "      matrix: [invalid, 1.0]\n"
    res = transform_float_precision(yaml_src, decimals=6)
    assert "matrix: [invalid, 1]" in res
