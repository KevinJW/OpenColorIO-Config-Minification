import pytest


@pytest.fixture
def dag_test_yaml():
    """OCIO YAML with reference space ACES2065-1 and distinct TestSpace with matrix transform."""
    return """ocio_profile_version: 2.0

roles:
  default: Raw
  scene_linear: ACES2065-1

colorspaces:
  - !<ColorSpace>
    name: ACES2065-1

  - !<ColorSpace>
    name: Raw
    isdata: true

  - !<ColorSpace>
    name: TestSpace
    to_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
"""


def test_dag_fidelity_identical_configs(ocio_module, dag_test_yaml):
    """Identical configurations must return passed=True with zero delta and no errors."""
    orig = ocio_module.ocio.Config.CreateFromStream(dag_test_yaml)
    candidate = ocio_module.ocio.Config.CreateFromStream(dag_test_yaml)

    passed, max_delta, failed_conversions = ocio_module.verify_dag_fidelity(
        orig, candidate
    )
    assert passed is True
    assert max_delta == 0.0
    assert len(failed_conversions) == 0


def test_dag_fidelity_detects_matrix_perturbation(ocio_module, dag_test_yaml):
    """Perturbing a matrix transform must be detected as a fidelity failure with delta > tolerance."""
    orig = ocio_module.ocio.Config.CreateFromStream(dag_test_yaml)

    # Perturb the matrix transform for TestSpace
    perturbed_yaml = dag_test_yaml.replace(
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1",
        "1.5, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1",
    )
    candidate = ocio_module.ocio.Config.CreateFromStream(perturbed_yaml)

    passed, max_delta, failed_conversions = ocio_module.verify_dag_fidelity(
        orig, candidate, tol=1e-6
    )
    assert passed is False
    assert max_delta > 0.0
    assert any("TestSpace" in fail for fail in failed_conversions)


def test_dag_fidelity_tolerance_threshold(ocio_module, dag_test_yaml):
    """A perturbation within tolerance should pass, while exceeding tolerance must fail."""
    orig = ocio_module.ocio.Config.CreateFromStream(dag_test_yaml)

    # Perturbation delta ~ 1e-5
    perturbed_yaml = dag_test_yaml.replace(
        "1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1",
        "1.00001, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1",
    )
    candidate = ocio_module.ocio.Config.CreateFromStream(perturbed_yaml)

    passed_loose, delta_loose, _ = ocio_module.verify_dag_fidelity(
        orig, candidate, tol=1e-3
    )
    assert passed_loose is True

    passed_strict, delta_strict, _ = ocio_module.verify_dag_fidelity(
        orig, candidate, tol=1e-7
    )
    assert passed_strict is False
    assert delta_strict > 1e-7


def test_dag_fidelity_displays_and_views(
    ocio_module, sample_ocio_config, sample_config_text
):
    """Assert DAG fidelity evaluates display and view transforms accurately."""
    candidate = ocio_module.ocio.Config.CreateFromStream(sample_config_text)
    passed, max_delta, fails = ocio_module.verify_dag_fidelity(
        sample_ocio_config, candidate
    )
    assert passed is True
    assert max_delta == 0.0
    assert len(fails) == 0


def test_fidelity_verifier_orig_cache(
    ocio_module, sample_ocio_config, sample_config_text
):
    """FidelityVerifier should cache baseline transform outputs and support clear_cache()."""
    from ocio_minifier.verification import FidelityVerifier

    verifier = FidelityVerifier()
    candidate = ocio_module.ocio.Config.CreateFromStream(sample_config_text)

    assert len(verifier._orig_cache) == 0

    res1 = verifier.verify(sample_ocio_config, candidate)
    assert res1.passed is True
    assert id(sample_ocio_config) in verifier._orig_cache

    cached_entry = verifier._orig_cache[id(sample_ocio_config)]
    assert "ref_name" in cached_entry
    assert "fwd_outs" in cached_entry
    assert len(cached_entry["fwd_outs"]) > 0

    # Second run reuses cache
    res2 = verifier.verify(sample_ocio_config, candidate)
    assert res2.passed is True
    assert res2.max_delta == res1.max_delta

    # Clearing cache removes entries
    verifier.clear_cache()
    assert len(verifier._orig_cache) == 0


def test_fidelity_verifier_deduplicates_display_views(ocio_module):
    """FidelityVerifier should deduplicate displays and views sharing the same view_transform."""
    from ocio_minifier.verification import FidelityVerifier

    multi_display_yaml = """ocio_profile_version: 2.0

roles:
  default: Raw
  scene_linear: Raw

displays:
  Display1:
    - !<View> {name: ViewA, colorspace: Raw}
    - !<View> {name: ViewB, colorspace: Raw}
  Display2:
    - !<View> {name: ViewA, colorspace: Raw}
    - !<View> {name: ViewB, colorspace: Raw}

colorspaces:
  - !<ColorSpace>
    name: Raw
    isdata: true
"""
    orig = ocio_module.ocio.Config.CreateFromStream(multi_display_yaml)
    cand = ocio_module.ocio.Config.CreateFromStream(multi_display_yaml)

    verifier = FidelityVerifier()
    res = verifier.verify(orig, cand)

    assert res.passed is True
    # 4 total display views (2 displays x 2 views), but only 1 unique colorspace/view combination
    assert res.evaluated_views < 4
    assert res.evaluated_views == 1


def test_fidelity_verifier_different_display_colorspaces_not_deduplicated(ocio_module):
    """Views sharing view_transform name but having different display colorspaces must not be merged."""
    from ocio_minifier.verification import FidelityVerifier

    yaml_config = """ocio_profile_version: 2.0
roles: {default: Raw, scene_linear: Linear}
display_colorspaces:
  - !<ColorSpace> {name: SpaceA, to_display_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}}
  - !<ColorSpace> {name: SpaceB, to_display_reference: !<MatrixTransform> {matrix: [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1]}}
view_transforms:
  - !<ViewTransform> {name: CommonView, from_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}}
displays:
  DisplayA: [!<View> {name: ToneMapped, view_transform: CommonView, display_colorspace: SpaceA}]
  DisplayB: [!<View> {name: ToneMapped, view_transform: CommonView, display_colorspace: SpaceB}]
colorspaces:
  - !<ColorSpace> {name: Linear, isdata: false}
  - !<ColorSpace> {name: Raw, isdata: true}
"""
    orig = ocio_module.ocio.Config.CreateFromStream(yaml_config)
    cand = ocio_module.ocio.Config.CreateFromStream(yaml_config)

    verifier = FidelityVerifier()
    res = verifier.verify(orig, cand)

    assert res.passed is True
    # Must evaluate both views because SpaceA != SpaceB
    assert res.evaluated_views == 2


def test_fidelity_verifier_different_looks_not_deduplicated(ocio_module):
    """Views with identical view_transform and display_colorspace but different looks must not be merged."""
    from ocio_minifier.verification import FidelityVerifier

    yaml_config = """ocio_profile_version: 2.0
roles: {default: Raw, scene_linear: Raw}
display_colorspaces:
  - !<ColorSpace> {name: DispRaw, isdata: true}
looks:
  - !<Look> {name: DimLook, process_space: Raw, transform: !<MatrixTransform> {matrix: [0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 1]}}
view_transforms:
  - !<ViewTransform> {name: IdentityVT, from_scene_reference: !<MatrixTransform> {matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}}
displays:
  StandardDisplay:
    - !<View> {name: ViewNoLook, view_transform: IdentityVT, display_colorspace: DispRaw}
    - !<View> {name: ViewWithLook, view_transform: IdentityVT, display_colorspace: DispRaw, looks: DimLook}
colorspaces:
  - !<ColorSpace> {name: Raw, isdata: true}
"""
    orig = ocio_module.ocio.Config.CreateFromStream(yaml_config)
    cand = ocio_module.ocio.Config.CreateFromStream(yaml_config)

    verifier = FidelityVerifier()
    res = verifier.verify(orig, cand)

    assert res.passed is True
    # Must evaluate both views because one has looks: DimLook and one has no looks
    assert res.evaluated_views == 2


def test_fidelity_verifier_different_rules_not_deduplicated(ocio_module):
    """Views with identical transform parameters but different viewing rules must not be merged."""
    from ocio_minifier.verification import FidelityVerifier

    yaml_config = """ocio_profile_version: 2.0
roles: {default: Raw, scene_linear: Raw}
viewing_rules:
  - !<Rule> {name: RuleA, colorspaces: [Raw]}
  - !<Rule> {name: RuleB, colorspaces: [Raw]}
displays:
  Display1:
    - !<View> {name: View1, colorspace: Raw, rule: RuleA}
    - !<View> {name: View2, colorspace: Raw, rule: RuleB}
colorspaces:
  - !<ColorSpace> {name: Raw, isdata: true}
"""
    orig = ocio_module.ocio.Config.CreateFromStream(yaml_config)
    cand = ocio_module.ocio.Config.CreateFromStream(yaml_config)

    verifier = FidelityVerifier()
    res = verifier.verify(orig, cand)

    assert res.passed is True
    # Must evaluate both views because RuleA != RuleB
    assert res.evaluated_views == 2


def test_fidelity_verifier_shared_views_deduplicated(ocio_module):
    """Shared views referenced across multiple displays should be safely deduplicated."""
    from ocio_minifier.verification import FidelityVerifier

    yaml_config = """ocio_profile_version: 2.0
roles: {default: Raw, scene_linear: Raw}
shared_views:
  - !<View> {name: SharedRaw, colorspace: Raw}
displays:
  Disp1:
    - !<Views> [SharedRaw]
  Disp2:
    - !<Views> [SharedRaw]
colorspaces:
  - !<ColorSpace> {name: Raw, isdata: true}
"""
    orig = ocio_module.ocio.Config.CreateFromStream(yaml_config)
    cand = ocio_module.ocio.Config.CreateFromStream(yaml_config)

    verifier = FidelityVerifier()
    res = verifier.verify(orig, cand)

    assert res.passed is True
    # 2 displays referencing the same shared view -> deduplicated to 1
    assert res.evaluated_views == 1


def test_validate_with_ociocheck_valid(sample_config_text):
    """validate_with_ociocheck should pass on valid configs."""
    from ocio_minifier.verification import validate_with_ociocheck

    passed, msg = validate_with_ociocheck(sample_config_text)
    assert passed is True


def test_validate_with_ociocheck_missing_lut():
    """validate_with_ociocheck should fail when referenced external LUT file is missing."""
    import shutil

    from ocio_minifier.verification import validate_with_ociocheck

    if not shutil.which("ociocheck"):
        pytest.skip("ociocheck executable not found on PATH")

    invalid_yaml = """ocio_profile_version: 2.0
search_path: .
roles: {default: Raw, scene_linear: Raw}
displays:
  Disp:
    - !<View> {name: View, colorspace: Raw}
colorspaces:
  - !<ColorSpace>
    name: Raw
    isdata: true
    to_reference: !<FileTransform> {src: non_existent_file.cube}
"""
    passed, msg = validate_with_ociocheck(invalid_yaml)
    assert passed is False
    assert "non_existent_file" in msg.lower()
