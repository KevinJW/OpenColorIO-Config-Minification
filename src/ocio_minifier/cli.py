"""Command-line interface for OpenColorIO configuration minification and benchmarking."""

import argparse
import json
import os
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Sequence

from ocio_minifier import __version__
from ocio_minifier.benchmark import BenchmarkRunner, format_markdown_table
from ocio_minifier.pipeline import MinificationPipeline
from ocio_minifier.verification import (
    HAS_OCIO,
    FidelityVerifier,
    diff_serialized_configs,
    ocio,
)

DEFAULT_CONFIG_PATH = os.path.join(
    "configs", "studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio"
)


def create_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for ocio-minify."""
    parser = argparse.ArgumentParser(
        prog="ocio-minify",
        description="Minify OpenColorIO configuration files and verify mathematical DAG fidelity.",
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to source OCIO configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to write minified OCIO configuration (prints to stdout if omitted)",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=["syntactic", "aggressive"],
        default="syntactic",
        help="Compression preset: 'syntactic' (lossless) or 'aggressive' (lossy descriptions). Default: syntactic",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        action="store_true",
        help="Execute benchmark comparison across all transforms instead of writing minified config",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format for benchmark results (default: markdown)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify mathematical DAG fidelity against source configuration",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Numerical tolerance for DAG fidelity verification (default: 1e-6)",
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=5,
        help="Number of timing iterations to run for benchmark parse measurement (default: 5)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup parse iterations prior to benchmark timing (default: 1)",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=None,
        help="Decimals of precision for lossy float rounding (only applies to 'aggressive' preset). Default: None (disabled)",
    )
    parser.add_argument(
        "--preserve-invariants",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve row sums (unity gain) and channel symmetry during float rounding (default: True)",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Serialize original and minified configs using PyOpenColorIO and display unified diff",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not os.path.exists(args.config_path):
        sys.stderr.write(f"Error: Config file '{args.config_path}' not found.\n")
        return 1

    try:
        if args.config_path.lower().endswith(".ocioz"):
            if HAS_OCIO:
                cfg = ocio.Config.CreateFromFile(args.config_path)
                cfg.validate()
                source_content = cfg.serialize()
            else:
                with tempfile.TemporaryDirectory() as td:
                    subprocess.run(
                        ["ocioarchive", "--extract", args.config_path, "--dir", td],
                        capture_output=True,
                        check=True,
                    )  # nosec B603, B607
                    config_ocio = os.path.join(td, "config.ocio")
                    with open(config_ocio, encoding="utf-8") as f:
                        source_content = f.read()
        else:
            with open(args.config_path, encoding="utf-8") as f:
                source_content = f.read()
    except Exception as e:
        sys.stderr.write(f"Error reading '{args.config_path}': {e}\n")
        return 1

    # Mode 1: Benchmark Suite
    if args.benchmark:
        try:
            runner = BenchmarkRunner(
                verifier=FidelityVerifier(tolerance=args.tolerance),
                warmup_iterations=args.warmup,
                timing_iterations=args.iterations,
            )
            results = runner.run_suite(source_content)
        except Exception as e:
            sys.stderr.write(f"Benchmark error: {e}\n")
            return 1

        if args.format == "json":
            json_data = [r.to_dict() for r in results]
            print(json.dumps(json_data, indent=2))
        else:
            print(
                f"Benchmarking transforms against: {os.path.basename(args.config_path)} ({len(source_content.encode('utf-8')) / 1024.0:.1f} KB)\n"
            )
            print(format_markdown_table(results))
        return 0

    # Mode 2: Minification Pipeline
    if args.preset == "aggressive":
        pipeline = MinificationPipeline.preset_aggressive(
            precision=args.precision,
            preserve_invariants=args.preserve_invariants,
        )
    else:
        pipeline = MinificationPipeline.preset_syntactic()

    minified = pipeline.run(source_content)

    # Optional Fidelity Verification
    if args.verify:
        if not HAS_OCIO:
            sys.stderr.write(
                "Error: PyOpenColorIO is required to run mathematical fidelity verification.\n"
            )
            return 1
        try:
            orig_cfg = ocio.Config.CreateFromStream(source_content)
            orig_cfg.validate()
            cand_cfg = ocio.Config.CreateFromStream(minified)
            cand_cfg.validate()
        except Exception as e:
            sys.stderr.write(f"Configuration validation failed: {e}\n")
            return 1

        verifier = FidelityVerifier(tolerance=args.tolerance)
        res = verifier.verify(orig_cfg, cand_cfg)
        if not res.passed:
            sys.stderr.write(
                f"Fidelity Verification FAILED: Max ΔRGB = {res.max_delta:.2e} (tolerance: {args.tolerance:.2e})\n"
            )
            for fail in res.failures[:10]:
                sys.stderr.write(f"  - {fail}\n")
            return 1
        sys.stderr.write(
            f"Fidelity Verification PASSED (Max ΔRGB = {res.max_delta:.2e})\n"
        )

    # Optional Serialized Configuration Diff
    if args.diff:
        if not HAS_OCIO:
            sys.stderr.write(
                "Error: PyOpenColorIO is required to serialize and diff configurations.\n"
            )
            return 1
        try:
            orig_cfg = ocio.Config.CreateFromStream(source_content)
            orig_cfg.validate()
            cand_cfg = ocio.Config.CreateFromStream(minified)
            cand_cfg.validate()
            diff_text = diff_serialized_configs(orig_cfg, cand_cfg)
            if diff_text:
                sys.stdout.write(diff_text)
            else:
                sys.stderr.write(
                    "Serialized configurations are semantically identical (0 diff lines).\n"
                )
        except Exception as e:
            sys.stderr.write(f"Diff generation failed: {e}\n")
            return 1

        if not args.output:
            return 0

    # Output Handling
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(minified)
            orig_len = len(source_content.encode("utf-8"))
            min_len = len(minified.encode("utf-8"))
            reduction = ((orig_len - min_len) / orig_len) * 100.0
            sys.stderr.write(
                f"Wrote minified configuration to '{args.output}' ({orig_len / 1024:.1f} KB -> {min_len / 1024:.1f} KB, -{reduction:.1f}%)\n"
            )
        except Exception as e:
            sys.stderr.write(f"Error writing output to '{args.output}': {e}\n")
            return 1
    else:
        sys.stdout.write(minified)

    return 0


if __name__ == "__main__":
    sys.exit(main())
