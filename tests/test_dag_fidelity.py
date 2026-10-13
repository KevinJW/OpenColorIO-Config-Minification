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


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
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


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
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


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
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


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
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
