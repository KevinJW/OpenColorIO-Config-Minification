import os

import pytest

from tests.test_basic import ALL_CONFIG_FILES


@pytest.mark.skipif(
    not pytest.importorskip("PyOpenColorIO", reason="PyOpenColorIO required"), reason=""
)
class TestPipelineIntegration:
    """End-to-end integration tests verifying every transform on the studio OCIO config."""

    def test_transform_elide_defaults_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        transformed = ocio_module.transform_elide_defaults(sample_config_text)
        assert len(transformed) < len(sample_config_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_transform_compact_amf_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        transformed = ocio_module.transform_compact_amf_scalars(sample_config_text)
        assert len(transformed) < len(sample_config_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_transform_flow_transforms_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        transformed = ocio_module.transform_flow_transforms(sample_config_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_transform_yaml_anchors_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        transformed = ocio_module.transform_yaml_anchors(sample_config_text)
        assert len(transformed) < len(sample_config_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_transform_strip_descriptions_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        transformed = ocio_module.transform_strip_descriptions(sample_config_text)
        assert len(transformed) < len(sample_config_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(transformed)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_pipeline_syntactic_combined_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        pipeline = ocio_module.transform_yaml_anchors(
            ocio_module.transform_flow_transforms(
                ocio_module.transform_compact_amf_scalars(
                    ocio_module.transform_elide_defaults(sample_config_text)
                )
            )
        )
        # Reduction should be at least 10%
        ratio = len(pipeline) / len(sample_config_text)
        assert ratio <= 0.90

        min_cfg = ocio_module.ocio.Config.CreateFromStream(pipeline)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    def test_pipeline_max_lossy_combined_fidelity(
        self, ocio_module, sample_ocio_config, sample_config_text
    ):
        syntactic = ocio_module.transform_yaml_anchors(
            ocio_module.transform_flow_transforms(
                ocio_module.transform_compact_amf_scalars(
                    ocio_module.transform_elide_defaults(sample_config_text)
                )
            )
        )
        max_lossy = ocio_module.transform_strip_descriptions(syntactic)

        # Reduction should be at least 19%
        ratio = len(max_lossy) / len(sample_config_text)
        assert ratio <= 0.81

        min_cfg = ocio_module.ocio.Config.CreateFromStream(max_lossy)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(
            sample_ocio_config, min_cfg
        )
        assert passed is True
        assert max_delta == 0.0
        assert len(fails) == 0

    @pytest.mark.parametrize("config_filename", ALL_CONFIG_FILES)
    def test_pipeline_syntactic_fidelity_all_configs(
        self, ocio_module, config_filename
    ):
        """Verify lossless syntactic pipeline yields 100% DAG fidelity across all builtin configs."""
        config_path = os.path.join("configs", config_filename)
        with open(config_path, encoding="utf-8") as f:
            source_text = f.read()

        orig_cfg = ocio_module.ocio.Config.CreateFromStream(source_text)
        orig_cfg.validate()

        pipeline = ocio_module.MinificationPipeline.preset_syntactic()
        minified_text = pipeline.run(source_text)

        min_cfg = ocio_module.ocio.Config.CreateFromStream(minified_text)
        min_cfg.validate()

        passed, max_delta, fails = ocio_module.verify_dag_fidelity(orig_cfg, min_cfg)
        assert passed is True, f"Fidelity failed for {config_filename}: {fails[:3]}"
        assert max_delta == 0.0
