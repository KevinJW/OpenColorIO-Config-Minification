"""Benchmark suite execution and metric calculation for OCIO minification."""

import gzip
import os
import subprocess  # nosec B404
import tempfile
import time
from typing import Any

from ocio_minifier.models import BenchmarkResult
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.transforms import (
    CompactAmfScalarsTransform,
    ElideDefaultsTransform,
    FlowTransformsTransform,
    StripDescriptionsTransform,
    YamlAnchorsTransform,
)
from ocio_minifier.verification import HAS_OCIO, FidelityVerifier, ocio


class BenchmarkRunner:
    """Executes transformation benchmarks and measures compression, parse speed, and fidelity."""

    def __init__(self, verifier: FidelityVerifier | None = None):
        self.verifier = verifier or FidelityVerifier()

    def benchmark_stage(
        self,
        name: str,
        content: str,
        baseline_bytes: int,
        orig_cfg: Any | None = None,
    ) -> BenchmarkResult:
        """Measure performance and fidelity of a single minification stage."""
        encoded = content.encode("utf-8")
        raw_size = len(encoded)
        gzip_size = len(gzip.compress(encoded, compresslevel=9))

        parse_time_ms = 0.0
        max_delta = 0.0
        fidelity_pass = False

        if HAS_OCIO:
            start = time.perf_counter()
            try:
                min_cfg = ocio.Config.CreateFromStream(content)
                min_cfg.validate()
                parse_time_ms = (time.perf_counter() - start) * 1000.0

                if orig_cfg is not None:
                    res = self.verifier.verify(orig_cfg, min_cfg)
                    max_delta = res.max_delta
                    fidelity_pass = res.passed
                else:
                    fidelity_pass = True
            except Exception:
                fidelity_pass = False
        else:
            # Fallback to CLI ociocheck if PyOpenColorIO is not installed
            with tempfile.NamedTemporaryFile("w", suffix=".ocio", delete=False) as f:
                f.write(content)
                tmp_name = f.name
            try:
                start = time.perf_counter()
                res_proc = subprocess.run(
                    ["ociocheck", "--file", tmp_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )  # nosec B603, B607
                parse_time_ms = (time.perf_counter() - start) * 1000.0
                fidelity_pass = res_proc.returncode == 0
            finally:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)

        return BenchmarkResult(
            name=name,
            raw_bytes=raw_size,
            baseline_bytes=baseline_bytes,
            gzip_bytes=gzip_size,
            parse_time_ms=parse_time_ms,
            max_delta=max_delta,
            fidelity_passed=fidelity_pass,
        )

    def run_suite(self, source_text: str) -> list[BenchmarkResult]:
        """Run all standard benchmark stages against source OCIO configuration text."""
        baseline_bytes = len(source_text.encode("utf-8"))
        orig_cfg = None

        if HAS_OCIO:
            try:
                orig_cfg = ocio.Config.CreateFromStream(source_text)
                orig_cfg.validate()
            except Exception as e:
                raise ValueError(f"Failed to parse source config: {e}") from e

        results: list[BenchmarkResult] = []

        # 0. Baseline
        results.append(
            self.benchmark_stage(
                "Baseline (Unmodified)", source_text, baseline_bytes, orig_cfg=None
            )
        )

        # 1. Default Field Elision
        t_elide = ElideDefaultsTransform().apply(source_text)
        results.append(
            self.benchmark_stage(
                "Default Field Elision", t_elide, baseline_bytes, orig_cfg
            )
        )

        # 2. Compact AMF Scalars
        t_amf = CompactAmfScalarsTransform().apply(source_text)
        results.append(
            self.benchmark_stage("Compact AMF Scalars", t_amf, baseline_bytes, orig_cfg)
        )

        # 3. Flow Transform Inlining
        t_flow = FlowTransformsTransform().apply(source_text)
        results.append(
            self.benchmark_stage(
                "Flow Transform Inlining", t_flow, baseline_bytes, orig_cfg
            )
        )

        # 4. CDL Transform Flow Inlining
        from ocio_minifier.transforms import FlowCdlTransformsTransform

        t_cdl = FlowCdlTransformsTransform().apply(source_text)
        results.append(
            self.benchmark_stage("CDL Flow Inlining", t_cdl, baseline_bytes, orig_cfg)
        )

        # 5. YAML Anchors & Aliases
        t_yaml = YamlAnchorsTransform().apply(source_text)
        results.append(
            self.benchmark_stage(
                "YAML Anchors & Aliases", t_yaml, baseline_bytes, orig_cfg
            )
        )

        # 6. Strip Descriptions (Lossy)
        t_desc = StripDescriptionsTransform().apply(source_text)
        results.append(
            self.benchmark_stage(
                "Strip Descriptions (Lossy)", t_desc, baseline_bytes, orig_cfg
            )
        )

        # 7. Float Precision Rounding (Lossy)
        from ocio_minifier.transforms import FloatPrecisionTransform

        t_float = FloatPrecisionTransform(decimals=7).apply(source_text)
        results.append(
            self.benchmark_stage(
                "Float Rounding [7 Decimals] (Lossy)", t_float, baseline_bytes, orig_cfg
            )
        )

        # 8. Combined (Syntactic Only)
        t_syn = MinificationPipeline.preset_syntactic().run(source_text)
        results.append(
            self.benchmark_stage(
                "Combined (Syntactic Only)", t_syn, baseline_bytes, orig_cfg
            )
        )

        # 9. Combined (Max / Lossy Desc)
        t_max = MinificationPipeline.preset_aggressive().run(source_text)
        results.append(
            self.benchmark_stage(
                "Combined (Max / Lossy Desc)", t_max, baseline_bytes, orig_cfg
            )
        )

        return results


def format_markdown_table(results: list[BenchmarkResult]) -> str:
    """Format benchmark results into a clean GitHub-flavored markdown table."""
    headers = [
        "Transform",
        "Raw Size",
        "Raw Delta",
        "Gzip Size",
        "Parse Time",
        "Max ΔRGB",
        "DAG Fidelity",
    ]
    alignments = [":---", ":---:", ":---:", ":---:", ":---:", ":---:", ":---:"]

    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join(alignments)} |",
    ]

    for r in results:
        lines.append(
            f"| {r.name} | {r.raw_kb:.2f} KB | {r.reduction_pct:.1f}% | "
            f"{r.gzip_kb:.2f} KB | {r.parse_time_ms:.2f} ms | "
            f"{r.max_delta:.2e} | {'PASS' if r.fidelity_passed else 'FAIL'} |"
        )

    return "\n".join(lines)


def run_benchmark(
    name: str, content: str, baseline_bytes: int, orig_cfg: Any | None = None
) -> dict[str, str]:
    """Legacy helper returning formatted dictionary."""
    runner = BenchmarkRunner()
    result = runner.benchmark_stage(name, content, baseline_bytes, orig_cfg)
    return result.to_dict()
