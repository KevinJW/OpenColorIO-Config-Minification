def test_strip_single_line_double_quotes(ocio_module):
    """Single line description in double quotes should be stripped."""
    yaml_src = (
        'name: test_cs\ndescription: "Standard sRGB transfer curve"\nfamily: Displays\n'
    )
    result = ocio_module.transform_strip_descriptions(yaml_src)
    assert 'description: "Standard sRGB transfer curve"' not in result
    assert "name: test_cs" in result
    assert "family: Displays" in result


def test_strip_single_line_single_quotes(ocio_module):
    """Single line description in single quotes should be stripped."""
    yaml_src = (
        "name: test_cs\ndescription: 'Standard sRGB transfer curve'\nfamily: Displays\n"
    )
    result = ocio_module.transform_strip_descriptions(yaml_src)
    assert "description: 'Standard sRGB transfer curve'" not in result
    assert "name: test_cs" in result
    assert "family: Displays" in result


def test_strip_single_line_unquoted(ocio_module):
    """Single line unquoted description should be stripped."""
    yaml_src = (
        "name: test_cs\ndescription: Standard sRGB transfer curve\nfamily: Displays\n"
    )
    result = ocio_module.transform_strip_descriptions(yaml_src)
    assert "description: Standard sRGB transfer curve" not in result
    assert "name: test_cs" in result
    assert "family: Displays" in result


def test_strip_multiline_block_preserves_subsequent_sections(ocio_module):
    """Multiline block scalar description must be stripped without consuming following top-level keys."""
    yaml_src = (
        "name: my_config\n"
        "description: |\n"
        "  Academy Color Encoding System\n"
        "  -----------------------------\n"
        "\n"
        "  This config includes a wide variety of transforms.\n"
        "\n"
        "roles:\n"
        "  default: Raw\n"
        "  scene_linear: ACEScg\n"
        "\n"
        "file_rules:\n"
        "  - !<Rule> {name: Default, colorspace: Raw}\n"
    )
    result = ocio_module.transform_strip_descriptions(yaml_src)
    assert "description:" not in result
    assert "Academy Color Encoding System" not in result
    assert "roles:" in result
    assert "default: Raw" in result
    assert "file_rules:" in result


def test_strip_indented_multiline_block_preserves_sibling_properties(ocio_module):
    """Indented multiline block description within an element must not consume sibling keys."""
    yaml_src = (
        "colorspaces:\n"
        "  - !<ColorSpace>\n"
        "    name: ACES2065-1\n"
        "    description: |\n"
        "      The ACES2065-1 linear reference space.\n"
        "      Includes wide-gamut primaries AP0.\n"
        "    family: ACES\n"
        "    bitdepth: 32f\n"
    )
    result = ocio_module.transform_strip_descriptions(yaml_src)
    assert "description:" not in result
    assert "The ACES2065-1 linear reference space" not in result
    assert "name: ACES2065-1" in result
    assert "family: ACES" in result
    assert "bitdepth: 32f" in result


def test_strip_descriptions_idempotency(ocio_module):
    """Applying transform_strip_descriptions repeatedly should produce identical text."""
    yaml_src = (
        "name: test\n"
        "description: |\n"
        "  Some multiline description.\n"
        "roles:\n"
        "  default: Raw\n"
    )
    pass1 = ocio_module.transform_strip_descriptions(yaml_src)
    pass2 = ocio_module.transform_strip_descriptions(pass1)
    assert pass1 == pass2


def test_strip_descriptions_maintains_valid_config(ocio_module, minimal_ocio_yaml):
    """Stripping descriptions from an OCIO config must yield a valid, parseable config."""
    yaml_with_desc = (
        "description: |\n  Config-level description.\n\n"
    ) + minimal_ocio_yaml
    result = ocio_module.transform_strip_descriptions(yaml_with_desc)
    cfg = ocio_module.ocio.Config.CreateFromStream(result)
    cfg.validate()
