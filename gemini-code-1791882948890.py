"""Backward-compatible entry point delegating to ocio_minifier."""

import os
import sys

from ocio_minifier import (
    DEFAULT_PIXEL_GRID,
    HAS_OCIO,
    BenchmarkRunner,
    FidelityVerifier,
    MinificationPipeline,
    format_markdown_table,
    run_benchmark,
    transform_compact_amf_scalars,
    transform_elide_defaults,
    transform_flow_transforms,
    transform_strip_descriptions,
    transform_yaml_anchors,
    verify_dag_fidelity,
)
from ocio_minifier.verification import ocio

TEST_PIXEL_GRID = DEFAULT_PIXEL_GRID

__all__ = [
    "DEFAULT_PIXEL_GRID",
    "HAS_OCIO",
    "TEST_PIXEL_GRID",
    "BenchmarkRunner",
    "FidelityVerifier",
    "MinificationPipeline",
    "format_markdown_table",
    "main",
    "ocio",
    "run_benchmark",
    "transform_compact_amf_scalars",
    "transform_elide_defaults",
    "transform_flow_transforms",
    "transform_strip_descriptions",
    "transform_yaml_anchors",
    "verify_dag_fidelity",
]


def main(source_file: str):
    if not os.path.exists(source_file):
        print(f"Error: Target config '{source_file}' not found.")
        sys.exit(1)

    with open(source_file, encoding="utf-8") as f:
        original = f.read()

    baseline_bytes = len(original.encode("utf-8"))
    print(
        f"Benchmarking transforms against: {os.path.basename(source_file)} ({baseline_bytes / 1024:.1f} KB)\n"
    )

    runner = BenchmarkRunner()
    results = runner.run_suite(original)
    print(format_markdown_table(results))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        default_path = os.path.join(
            "configs", "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio"
        )
        target = (
            default_path
            if os.path.exists(default_path)
            else "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio"
        )
    main(target)
