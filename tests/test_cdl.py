from ocio_minifier.transforms.cdl import transform_flow_cdl_transforms


def test_cdl_transform_inlining():
    yaml_src = (
        "  - !<CDLTransform>\n"
        "    slope: [1.0, 1.0, 1.0]\n"
        "    offset: [0.1,\n"
        "             0.2,\n"
        "             0.3]\n"
        "    power: [1.1, 1.1, 1.1]\n"
        "    sat: 1.0\n"
    )
    res = transform_flow_cdl_transforms(yaml_src)
    assert "slope: [1.0, 1.0, 1.0]" in res
    assert "offset: [0.1, 0.2, 0.3]" in res
    assert "power: [1.1, 1.1, 1.1]" in res
    assert "sat: 1.0\n" in res
