"""Benchmark suite execution and metric calculation for OCIO minification."""

import gc
import gzip
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from typing import Any

import PyOpenColorIO as ocio

from ocio_minifier.models import BenchmarkResult
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.transforms import (
    CompactAmfScalarsTransform,
    ElideDefaultsTransform,
    FloatPrecisionTransform,
    FlowCdlTransformsTransform,
    FlowTransformsTransform,
    StripDescriptionsTransform,
    YamlAnchorsTransform,
)
from ocio_minifier.verification import FidelityVerifier, validate_with_ociocheck


def create_ocio_archive(content: Any, output_archive_path: str) -> None:
    """Create an OCIO Archive (.ocioz) using PyOpenColorIO Config.archive()."""
    working_dir = os.path.dirname(os.path.abspath(output_archive_path))
    if not isinstance(content, str) and hasattr(content, "archive"):
        orig_dir = content.getWorkingDir()
        try:
            content.setWorkingDir(working_dir)
            content.archive(output_archive_path)
        finally:
            content.setWorkingDir(orig_dir)
    else:
        cfg = ocio.Config.CreateFromStream(content)
        cfg.setWorkingDir(working_dir)
        cfg.archive(output_archive_path)


def get_ocioz_archive_size(content: str) -> int:
    """Create a temporary .ocioz archive using OCIO archiving and return its byte size."""
    with tempfile.TemporaryDirectory() as td:
        archive_path = os.path.join(td, "config.ocioz")
        create_ocio_archive(content, archive_path)
        return os.path.getsize(archive_path)


class BenchmarkRunner:
    """Executes transformation benchmarks and measures compression, parse speed, and fidelity."""

    def __init__(
        self,
        verifier: FidelityVerifier | None = None,
        warmup_iterations: int = 1,
        timing_iterations: int = 5,
        statistic: str = "median",
    ):
        self.verifier = verifier or FidelityVerifier()
        self.warmup_iterations = max(1, warmup_iterations)
        self.timing_iterations = max(1, timing_iterations)
        self.statistic = statistic

    def _measure_timings_and_fidelity(
        self,
        load_fn: Any,
        orig_cfg: Any | None = None,
        skip_verify: bool = False,
    ) -> tuple[
        float,
        float | None,
        float | None,
        float | None,
        float | None,
        float,
        bool,
    ]:
        """Execute warmup, timing iterations with GC isolation, and verify DAG fidelity."""
        parse_time_ms = 0.0
        parse_time_min_ms: float | None = None
        parse_time_max_ms: float | None = None
        parse_time_mean_ms: float | None = None
        parse_time_stddev_ms: float | None = None
        max_delta = 0.0
        fidelity_pass = False

        try:
            # 1. Warmup and structural validation
            warm_cfg = load_fn()
            warm_cfg.validate()
            for _ in range(self.warmup_iterations - 1):
                load_fn()

            # 2. Repeated measurement iterations with GC isolation
            timings: list[float] = []
            last_cfg = None
            gc.collect()
            gc_was_enabled = gc.isenabled()
            gc.disable()
            try:
                for _ in range(self.timing_iterations):
                    start = time.perf_counter()
                    last_cfg = load_fn()
                    end = time.perf_counter()
                    timings.append((end - start) * 1000.0)
            finally:
                if gc_was_enabled:
                    gc.enable()

            if self.statistic == "min":
                parse_time_ms = min(timings)
            elif self.statistic == "mean":
                parse_time_ms = statistics.mean(timings)
            else:  # default "median"
                parse_time_ms = statistics.median(timings)

            parse_time_min_ms = min(timings)
            parse_time_max_ms = max(timings)
            parse_time_mean_ms = statistics.mean(timings)
            parse_time_stddev_ms = (
                statistics.stdev(timings) if len(timings) > 1 else 0.0
            )

            min_cfg = last_cfg

            if skip_verify:
                max_delta = 0.0
                fidelity_pass = min_cfg is not None
            elif orig_cfg is not None and min_cfg is not None:
                res = self.verifier.verify(orig_cfg, min_cfg)
                max_delta = res.max_delta
                fidelity_pass = res.passed
            else:
                fidelity_pass = min_cfg is not None
        except Exception:
            fidelity_pass = False

        return (
            parse_time_ms,
            parse_time_min_ms,
            parse_time_max_ms,
            parse_time_mean_ms,
            parse_time_stddev_ms,
            max_delta,
            fidelity_pass,
        )

    def benchmark_stage(
        self,
        name: str,
        content: str,
        baseline_bytes: int,
        orig_cfg: Any | None = None,
        archive_bytes: int | None = None,
        archive_path: str | None = None,
        baseline_text: str | None = None,
        skip_verify: bool = False,
    ) -> BenchmarkResult:
        """Measure performance and fidelity of a single minification stage."""
        encoded = content.encode("utf-8")
        raw_size = len(encoded)
        gzip_size = len(gzip.compress(encoded, compresslevel=9))
        is_identity = skip_verify or (
            baseline_text is not None and content == baseline_text
        )

        (
            parse_time_ms,
            parse_time_min_ms,
            parse_time_max_ms,
            parse_time_mean_ms,
            parse_time_stddev_ms,
            max_delta,
            fidelity_pass,
        ) = self._measure_timings_and_fidelity(
            lambda: ocio.Config.CreateFromStream(content),
            orig_cfg,
            skip_verify=is_identity,
        )

        # Measure archive (.ocioz) load timing directly from ocioz file
        owned_td: tempfile.TemporaryDirectory[str] | None = None
        target_archive = archive_path
        if target_archive is None:
            owned_td = tempfile.TemporaryDirectory()
            target_archive = os.path.join(owned_td.name, "stage.ocioz")
            create_ocio_archive(content, target_archive)

        try:
            archive_size = (
                archive_bytes
                if archive_bytes is not None
                else os.path.getsize(target_archive)
            )

            (
                archive_parse_time_ms,
                archive_parse_time_min_ms,
                archive_parse_time_max_ms,
                archive_parse_time_mean_ms,
                archive_parse_time_stddev_ms,
                _,
                _,
            ) = self._measure_timings_and_fidelity(
                lambda: ocio.Config.CreateFromFile(target_archive),
                orig_cfg=None,
            )
        finally:
            if owned_td is not None:
                owned_td.cleanup()

        return BenchmarkResult(
            name=name,
            raw_bytes=raw_size,
            baseline_bytes=baseline_bytes,
            gzip_bytes=gzip_size,
            archive_bytes=archive_size,
            parse_time_ms=parse_time_ms,
            max_delta=max_delta,
            fidelity_passed=fidelity_pass,
            parse_time_min_ms=parse_time_min_ms,
            parse_time_max_ms=parse_time_max_ms,
            parse_time_mean_ms=parse_time_mean_ms,
            parse_time_stddev_ms=parse_time_stddev_ms,
            archive_parse_time_ms=archive_parse_time_ms,
            archive_parse_time_min_ms=archive_parse_time_min_ms,
            archive_parse_time_max_ms=archive_parse_time_max_ms,
            archive_parse_time_mean_ms=archive_parse_time_mean_ms,
            archive_parse_time_stddev_ms=archive_parse_time_stddev_ms,
        )

    def benchmark_archive_stage(
        self,
        name: str,
        archive_path: str,
        baseline_bytes: int,
        orig_cfg: Any | None = None,
    ) -> BenchmarkResult:
        """Measure performance and fidelity of an OCIO Archive (.ocioz) stage."""
        archive_size = os.path.getsize(archive_path)
        with open(archive_path, "rb") as f:
            archive_data = f.read()
        gzip_size = len(gzip.compress(archive_data, compresslevel=9))

        (
            parse_time_ms,
            parse_time_min_ms,
            parse_time_max_ms,
            parse_time_mean_ms,
            parse_time_stddev_ms,
            max_delta,
            fidelity_pass,
        ) = self._measure_timings_and_fidelity(
            lambda: ocio.Config.CreateFromFile(archive_path),
            orig_cfg,
        )

        return BenchmarkResult(
            name=name,
            raw_bytes=archive_size,
            baseline_bytes=baseline_bytes,
            gzip_bytes=gzip_size,
            archive_bytes=archive_size,
            parse_time_ms=parse_time_ms,
            max_delta=max_delta,
            fidelity_passed=fidelity_pass,
            parse_time_min_ms=parse_time_min_ms,
            parse_time_max_ms=parse_time_max_ms,
            parse_time_mean_ms=parse_time_mean_ms,
            parse_time_stddev_ms=parse_time_stddev_ms,
            archive_parse_time_ms=parse_time_ms,
            archive_parse_time_min_ms=parse_time_min_ms,
            archive_parse_time_max_ms=parse_time_max_ms,
            archive_parse_time_mean_ms=parse_time_mean_ms,
            archive_parse_time_stddev_ms=parse_time_stddev_ms,
        )

    @staticmethod
    def get_standard_stages() -> list[tuple[str, Callable[[str], str], str]]:
        """Return ordered list of standard transform benchmark stage definitions: (name, transform_fn, tag)."""
        return [
            (
                "Default Field Elision",
                lambda s: ElideDefaultsTransform().apply(s),
                "elide",
            ),
            (
                "Compact AMF Scalars",
                lambda s: CompactAmfScalarsTransform().apply(s),
                "amf",
            ),
            (
                "Flow Transform Inlining",
                lambda s: FlowTransformsTransform().apply(s),
                "flow",
            ),
            (
                "CDL Flow Inlining",
                lambda s: FlowCdlTransformsTransform().apply(s),
                "cdl",
            ),
            (
                "YAML Anchors & Aliases",
                lambda s: YamlAnchorsTransform().apply(s),
                "yaml",
            ),
            (
                "Strip Descriptions (Lossy)",
                lambda s: StripDescriptionsTransform().apply(s),
                "desc",
            ),
            (
                "Float Rounding [7 Decimals] (Lossy)",
                lambda s: FloatPrecisionTransform(decimals=7).apply(s),
                "float",
            ),
            (
                "Combined (Syntactic Only)",
                lambda s: MinificationPipeline.preset_syntactic().run(s),
                "syn",
            ),
            (
                "Combined (Max / Lossy Desc)",
                lambda s: MinificationPipeline.preset_aggressive().run(s),
                "max",
            ),
        ]

    def _execute_stage(
        self,
        name: str,
        content: str,
        baseline_bytes: int,
        orig_cfg: Any,
        archive_path: str,
        source_text: str,
    ) -> BenchmarkResult:
        """Run a single benchmark stage with an archive file."""
        create_ocio_archive(content, archive_path)
        return self.benchmark_stage(
            name,
            content,
            baseline_bytes,
            orig_cfg,
            archive_path=archive_path,
            baseline_text=source_text,
        )

    def run_suite(self, source_text: str) -> list[BenchmarkResult]:
        """Run all standard benchmark stages against source OCIO configuration text."""
        baseline_bytes = len(source_text.encode("utf-8"))
        try:
            orig_cfg = ocio.Config.CreateFromStream(source_text)
            orig_cfg.validate()
        except Exception as e:
            raise ValueError(f"Failed to parse source config: {e}") from e

        results: list[BenchmarkResult] = []

        # Suppress repetitive OCIO INFO log outputs during benchmark loop
        prev_log_level = ocio.GetLoggingLevel()
        ocio.SetLoggingLevel(ocio.LOGGING_LEVEL_WARNING)

        try:
            with tempfile.TemporaryDirectory() as suite_td:
                # 0. Baseline (Unmodified) - archive created once and reused for stage 10
                baseline_archive = os.path.join(suite_td, "baseline.ocioz")
                create_ocio_archive(orig_cfg, baseline_archive)

                # Deep validation with ociocheck (verifies external LUTs and inactive spaces)
                ociocheck_ok, ociocheck_msg = validate_with_ociocheck(baseline_archive)
                if not ociocheck_ok:
                    sys.stderr.write(
                        f"Warning: ociocheck validation reported issues: {ociocheck_msg}\n"
                    )

                results.append(
                    self.benchmark_stage(
                        "Baseline (Unmodified)",
                        source_text,
                        baseline_bytes,
                        orig_cfg=None,
                        archive_path=baseline_archive,
                    )
                )

                # 1-9. Standard Transform Stages
                max_archive = os.path.join(suite_td, "max.ocioz")
                for (
                    stage_name,
                    transform_fn,
                    tag,
                ) in self.get_standard_stages():
                    content = transform_fn(source_text)
                    archive_path = (
                        max_archive
                        if tag == "max"
                        else os.path.join(suite_td, f"{tag}.ocioz")
                    )
                    results.append(
                        self._execute_stage(
                            stage_name,
                            content,
                            baseline_bytes,
                            orig_cfg,
                            archive_path,
                            source_text,
                        )
                    )

                # 10. Native OCIO Archive (.ocioz) - reuses baseline_archive!
                results.append(
                    self.benchmark_archive_stage(
                        "Native OCIO Archive (.ocioz)",
                        baseline_archive,
                        baseline_bytes,
                        orig_cfg,
                    )
                )

                # 11. Minified OCIO Archive (.ocioz) - reuses max_archive!
                results.append(
                    self.benchmark_archive_stage(
                        "Minified OCIO Archive (.ocioz)",
                        max_archive,
                        baseline_bytes,
                        orig_cfg,
                    )
                )
        finally:
            ocio.SetLoggingLevel(prev_log_level)

        return results


def format_markdown_table(results: list[BenchmarkResult]) -> str:
    """Format benchmark results into a clean GitHub-flavored markdown table."""
    headers = [
        "Transform",
        "Raw Size",
        "Raw Delta",
        "Gzip Size",
        "Archive Size",
        "Parse Time (Mean ± Std)",
        "Archive Load Time (Mean ± Std)",
        "Max ΔRGB",
        "DAG Fidelity",
    ]
    alignments = [
        ":---",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
        ":---:",
    ]

    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join(alignments)} |",
    ]

    for r in results:
        lines.append(
            f"| {r.name} | {r.raw_size_str} | {r.delta_str} | "
            f"{r.gzip_size_str} | {r.archive_size_str} | {r.timing_str} | "
            f"{r.archive_timing_str} | {r.max_delta:.2e} | "
            f"{'PASS' if r.fidelity_passed else 'FAIL'} |"
        )

    return "\n".join(lines)


def run_benchmark(
    name: str, content: str, baseline_bytes: int, orig_cfg: Any | None = None
) -> dict[str, str]:
    """Legacy helper returning formatted dictionary."""
    runner = BenchmarkRunner()
    result = runner.benchmark_stage(name, content, baseline_bytes, orig_cfg)
    return result.to_dict()
