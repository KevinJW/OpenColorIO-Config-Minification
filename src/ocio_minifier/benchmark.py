"""Benchmark suite execution and metric calculation for OCIO minification."""

import gc
import gzip
import os
import statistics
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


def create_ocio_archive(content: Any, output_archive_path: str) -> None:
    """Create an OCIO Archive (.ocioz) using PyOpenColorIO Config.archive() or ocioarchive CLI."""
    native_archive_success = False
    working_dir = os.path.dirname(os.path.abspath(output_archive_path))

    if HAS_OCIO:
        try:
            if not isinstance(content, str) and hasattr(content, "archive"):
                orig_dir = content.getWorkingDir()
                try:
                    content.setWorkingDir(working_dir)
                    content.archive(output_archive_path)
                    native_archive_success = True
                finally:
                    content.setWorkingDir(orig_dir)
            elif isinstance(content, str):
                cfg = ocio.Config.CreateFromStream(content)
                cfg.setWorkingDir(working_dir)
                cfg.archive(output_archive_path)
                native_archive_success = True
        except Exception:
            native_archive_success = False

    if native_archive_success:
        return

    text_content = (
        content.serialize() if hasattr(content, "serialize") else str(content)
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".ocio", delete=False, encoding="utf-8"
    ) as f:
        f.write(text_content)
        tmp_config = f.name
    try:
        subprocess.run(
            ["ocioarchive", output_archive_path, "--iconfig", tmp_config],
            capture_output=True,
            check=True,
        )  # nosec B603, B607
    finally:
        if os.path.exists(tmp_config):
            os.remove(tmp_config)


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
        load_fn: Any | None,
        cli_cmd: list[str] | None,
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

        if HAS_OCIO and load_fn is not None:
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
                for _ in range(self.timing_iterations):
                    gc.collect(0)
                    gc_was_enabled = gc.isenabled()
                    gc.disable()
                    try:
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
        elif cli_cmd is not None:
            try:
                # Warmup
                for _ in range(self.warmup_iterations):
                    subprocess.run(
                        cli_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )  # nosec B603, B607

                timings_cli: list[float] = []
                last_returncode = 1
                for _ in range(self.timing_iterations):
                    start = time.perf_counter()
                    res_proc = subprocess.run(
                        cli_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )  # nosec B603, B607
                    end = time.perf_counter()
                    timings_cli.append((end - start) * 1000.0)
                    last_returncode = res_proc.returncode

                parse_time_ms = statistics.median(timings_cli)
                parse_time_min_ms = min(timings_cli)
                parse_time_max_ms = max(timings_cli)
                parse_time_mean_ms = statistics.mean(timings_cli)
                parse_time_stddev_ms = (
                    statistics.stdev(timings_cli) if len(timings_cli) > 1 else 0.0
                )
                fidelity_pass = last_returncode == 0
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

        if HAS_OCIO:
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
                None,
                orig_cfg,
                skip_verify=is_identity,
            )
        else:
            with tempfile.NamedTemporaryFile("w", suffix=".ocio", delete=False) as f:
                f.write(content)
                tmp_name = f.name
            try:
                (
                    parse_time_ms,
                    parse_time_min_ms,
                    parse_time_max_ms,
                    parse_time_mean_ms,
                    parse_time_stddev_ms,
                    max_delta,
                    fidelity_pass,
                ) = self._measure_timings_and_fidelity(
                    None,
                    ["ociocheck", "--file", tmp_name],
                    orig_cfg,
                )
            finally:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)

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

            load_archive_fn = (
                (lambda: ocio.Config.CreateFromFile(target_archive))
                if HAS_OCIO
                else None
            )
            cli_archive_cmd = ["ociocheck", "--iconfig", target_archive]

            (
                archive_parse_time_ms,
                archive_parse_time_min_ms,
                archive_parse_time_max_ms,
                archive_parse_time_mean_ms,
                archive_parse_time_stddev_ms,
                _,
                _,
            ) = self._measure_timings_and_fidelity(
                load_archive_fn,
                cli_archive_cmd,
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

        load_fn = (
            (lambda: ocio.Config.CreateFromFile(archive_path)) if HAS_OCIO else None
        )
        cli_cmd = ["ociocheck", "--iconfig", archive_path]

        (
            parse_time_ms,
            parse_time_min_ms,
            parse_time_max_ms,
            parse_time_mean_ms,
            parse_time_stddev_ms,
            max_delta,
            fidelity_pass,
        ) = self._measure_timings_and_fidelity(load_fn, cli_cmd, orig_cfg)

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

        # Suppress repetitive OCIO INFO log outputs during benchmark loop
        prev_log_level = None
        if HAS_OCIO:
            prev_log_level = ocio.GetLoggingLevel()
            ocio.SetLoggingLevel(ocio.LOGGING_LEVEL_WARNING)

        try:
            with tempfile.TemporaryDirectory() as suite_td:
                # 0. Baseline (Unmodified) - archive created once and reused for stage 10
                baseline_archive = os.path.join(suite_td, "baseline.ocioz")
                create_ocio_archive(
                    orig_cfg if orig_cfg is not None else source_text,
                    baseline_archive,
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

                # 1. Default Field Elision
                t_elide = ElideDefaultsTransform().apply(source_text)
                elide_archive = os.path.join(suite_td, "elide.ocioz")
                create_ocio_archive(t_elide, elide_archive)
                results.append(
                    self.benchmark_stage(
                        "Default Field Elision",
                        t_elide,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=elide_archive,
                        baseline_text=source_text,
                    )
                )

                # 2. Compact AMF Scalars
                t_amf = CompactAmfScalarsTransform().apply(source_text)
                amf_archive = os.path.join(suite_td, "amf.ocioz")
                create_ocio_archive(t_amf, amf_archive)
                results.append(
                    self.benchmark_stage(
                        "Compact AMF Scalars",
                        t_amf,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=amf_archive,
                        baseline_text=source_text,
                    )
                )

                # 3. Flow Transform Inlining
                t_flow = FlowTransformsTransform().apply(source_text)
                flow_archive = os.path.join(suite_td, "flow.ocioz")
                create_ocio_archive(t_flow, flow_archive)
                results.append(
                    self.benchmark_stage(
                        "Flow Transform Inlining",
                        t_flow,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=flow_archive,
                        baseline_text=source_text,
                    )
                )

                # 4. CDL Transform Flow Inlining
                from ocio_minifier.transforms import FlowCdlTransformsTransform

                t_cdl = FlowCdlTransformsTransform().apply(source_text)
                cdl_archive = os.path.join(suite_td, "cdl.ocioz")
                create_ocio_archive(t_cdl, cdl_archive)
                results.append(
                    self.benchmark_stage(
                        "CDL Flow Inlining",
                        t_cdl,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=cdl_archive,
                        baseline_text=source_text,
                    )
                )

                # 5. YAML Anchors & Aliases
                t_yaml = YamlAnchorsTransform().apply(source_text)
                yaml_archive = os.path.join(suite_td, "yaml.ocioz")
                create_ocio_archive(t_yaml, yaml_archive)
                results.append(
                    self.benchmark_stage(
                        "YAML Anchors & Aliases",
                        t_yaml,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=yaml_archive,
                        baseline_text=source_text,
                    )
                )

                # 6. Strip Descriptions (Lossy)
                t_desc = StripDescriptionsTransform().apply(source_text)
                desc_archive = os.path.join(suite_td, "desc.ocioz")
                create_ocio_archive(t_desc, desc_archive)
                results.append(
                    self.benchmark_stage(
                        "Strip Descriptions (Lossy)",
                        t_desc,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=desc_archive,
                        baseline_text=source_text,
                    )
                )

                # 7. Float Precision Rounding (Lossy)
                from ocio_minifier.transforms import FloatPrecisionTransform

                t_float = FloatPrecisionTransform(decimals=7).apply(source_text)
                float_archive = os.path.join(suite_td, "float.ocioz")
                create_ocio_archive(t_float, float_archive)
                results.append(
                    self.benchmark_stage(
                        "Float Rounding [7 Decimals] (Lossy)",
                        t_float,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=float_archive,
                        baseline_text=source_text,
                    )
                )

                # 8. Combined (Syntactic Only)
                t_syn = MinificationPipeline.preset_syntactic().run(source_text)
                syn_archive = os.path.join(suite_td, "syn.ocioz")
                create_ocio_archive(t_syn, syn_archive)
                results.append(
                    self.benchmark_stage(
                        "Combined (Syntactic Only)",
                        t_syn,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=syn_archive,
                        baseline_text=source_text,
                    )
                )

                # 9. Combined (Max / Lossy Desc)
                t_max = MinificationPipeline.preset_aggressive().run(source_text)
                max_archive = os.path.join(suite_td, "max.ocioz")
                create_ocio_archive(t_max, max_archive)
                results.append(
                    self.benchmark_stage(
                        "Combined (Max / Lossy Desc)",
                        t_max,
                        baseline_bytes,
                        orig_cfg,
                        archive_path=max_archive,
                        baseline_text=source_text,
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
            if prev_log_level is not None and HAS_OCIO:
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
