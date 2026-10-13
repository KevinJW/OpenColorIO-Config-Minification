def test_compact_single_amf_scalar(ocio_module):
    """Multiline block containing a single URN should be formatted as a single quoted string."""
    yaml_src = (
        "    amf_transform_ids: |\n"
        "      urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\n"
    )
    result = ocio_module.transform_compact_amf_scalars(yaml_src)
    expected = '    amf_transform_ids: "urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\\n"\n'
    assert result == expected


def test_compact_multiple_amf_scalars(ocio_module):
    """Multiline block containing multiple URNs should join them with escaped newlines."""
    yaml_src = (
        "    amf_transform_ids: |\n"
        "      urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\n"
        "      urn:aswf:ocio:transformId:1.0:ACES:ACEScg:1.0\n"
    )
    result = ocio_module.transform_compact_amf_scalars(yaml_src)
    assert (
        'amf_transform_ids: "urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\\nurn:aswf:ocio:transformId:1.0:ACES:ACEScg:1.0\\n"'
        in result
    )


def test_preserve_indentation(ocio_module):
    """Indentation of amf_transform_ids must be strictly preserved."""
    yaml_src = "        amf_transform_ids: |\n          urn:test:id\n"
    result = ocio_module.transform_compact_amf_scalars(yaml_src)
    assert result.startswith("        amf_transform_ids:")


def test_ignore_other_block_scalars(ocio_module):
    """Other YAML block scalars must not be modified by transform_compact_amf_scalars."""
    yaml_src = "    description: |\n      urn:some:urn:in:description\n"
    result = ocio_module.transform_compact_amf_scalars(yaml_src)
    assert result == yaml_src


def test_compact_amf_idempotency(ocio_module):
    """Applying the transform repeatedly must not re-escape or corrupt the string."""
    yaml_src = (
        "    amf_transform_ids: |\n"
        "      urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\n"
    )
    pass1 = ocio_module.transform_compact_amf_scalars(yaml_src)
    pass2 = ocio_module.transform_compact_amf_scalars(pass1)
    assert pass1 == pass2


def test_compact_amf_crlf_handling(ocio_module):
    """CRLF line endings should be handled consistently."""
    yaml_src = (
        "    amf_transform_ids: |\r\n"
        "      urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\r\n"
    )
    result = ocio_module.transform_compact_amf_scalars(yaml_src)
    assert (
        'amf_transform_ids: "urn:aswf:ocio:transformId:1.0:ACES:ACES2065-1:1.0\\n"'
        in result
    )
