import json
from pathlib import Path

import pytest

from ocio_minifier.cli import main


def test_cli_help(capsys):
    """--help should display usage and exit with code 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "usage: ocio-minify" in captured.out


def test_cli_version(capsys):
    """--version should output current package version and exit with code 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "ocio-minify 0.1.0" in captured.out


def test_cli_missing_file(capsys):
    """Non-existent configuration path should return exit code 1."""
    ret = main(["non_existent_config.ocio"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_cli_minify_to_file(tmp_path: Path):
    """Minifying to an output file should produce a smaller valid config."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    out_file = tmp_path / "minified.ocio"
    ret = main([str(source_file), "-o", str(out_file), "--preset", "syntactic"])
    assert ret == 0
    assert out_file.exists()
    assert out_file.stat().st_size < source_file.stat().st_size


def test_cli_minify_with_verify(tmp_path: Path):
    """Minifying with --verify should run fidelity verification and succeed."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    out_file = tmp_path / "minified_verified.ocio"
    ret = main([str(source_file), "-o", str(out_file), "--verify"])
    assert ret == 0
    assert out_file.exists()


def test_cli_minify_aggressive_with_precision(tmp_path: Path):
    """Minifying with aggressive preset, precision rounding, and invariant preservation."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    out_file = tmp_path / "minified_precision.ocio"
    ret = main(
        [
            str(source_file),
            "-o",
            str(out_file),
            "--preset",
            "aggressive",
            "--precision",
            "7",
            "--preserve-invariants",
            "--verify",
            "--tolerance",
            "0.05",
        ]
    )
    assert ret == 0
    assert out_file.exists()


def test_cli_benchmark_markdown(capsys):
    """Running benchmark mode with default markdown should print table."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main([str(source_file), "--benchmark", "--format", "markdown"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "| Transform | Raw Size |" in captured.out
    assert "| Archive Size |" in captured.out
    assert "| Archive Load Time (Mean ± Std) |" in captured.out
    assert "Baseline (Unmodified)" in captured.out
    assert "Native OCIO Archive (.ocioz)" in captured.out
    assert "Minified OCIO Archive (.ocioz)" in captured.out


def test_cli_benchmark_json(capsys):
    """Running benchmark mode with --format json should output valid JSON."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main([str(source_file), "--benchmark", "--format", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "Name" in data[0]
    assert "Raw (KB)" in data[0]
    assert "Archive Bytes" in data[0]
    assert "Archive (KB)" in data[0]
    assert "Archive Load (ms)" in data[0]


def test_cli_benchmark_with_iterations(capsys):
    """Running benchmark mode with custom iterations and warmup flags."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main([str(source_file), "--benchmark", "--iterations", "2", "--warmup", "1"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "| Transform | Raw Size |" in captured.out
    assert "| Archive Size |" in captured.out
    assert "| Archive Load Time (Mean ± Std) |" in captured.out


def test_cli_benchmark_ocioz_input(tmp_path, capsys):
    """Running benchmark mode with a .ocioz input file should unpack and run benchmarks."""
    from ocio_minifier.benchmark import create_ocio_archive

    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    archive_path = tmp_path / "test_input.ocioz"
    create_ocio_archive(source_file.read_text(encoding="utf-8"), str(archive_path))

    ret = main([str(archive_path), "--benchmark", "--iterations", "1", "--warmup", "0"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "| Transform | Raw Size |" in captured.out
    assert "| Archive Size |" in captured.out
    assert "| Archive Load Time (Mean ± Std) |" in captured.out
    assert "Native OCIO Archive (.ocioz)" in captured.out


def test_cli_minify_from_ocioz_input(tmp_path):
    """Running minify command with a .ocioz input file should produce valid minified output."""
    from ocio_minifier.benchmark import create_ocio_archive

    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    archive_path = tmp_path / "test_input.ocioz"
    create_ocio_archive(source_file.read_text(encoding="utf-8"), str(archive_path))

    out_file = tmp_path / "minified_from_archive.ocio"
    ret = main([str(archive_path), "-o", str(out_file)])
    assert ret == 0
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_cli_error_reading_file(tmp_path, capsys):
    """CLI should return 1 and log error when input file cannot be read."""
    ret = main([str(tmp_path)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_cli_error_benchmark_failure(tmp_path, capsys):
    """CLI benchmark mode should return 1 on invalid configuration YAML."""
    invalid_file = tmp_path / "bad.ocio"
    invalid_file.write_text("invalid: [yaml", encoding="utf-8")
    ret = main([str(invalid_file), "--benchmark"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Benchmark error" in captured.err


def test_cli_verify_failure_exit(capsys):
    """CLI --verify should return 1 when tolerance is violated."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main(
        [
            str(source_file),
            "--preset",
            "aggressive",
            "--precision",
            "3",
            "--verify",
            "--tolerance",
            "1e-12",
        ]
    )
    assert ret == 1
    captured = capsys.readouterr()
    assert "Fidelity Verification FAILED" in captured.err


def test_cli_verify_and_diff_combined(capsys):
    """Running CLI with both --verify and --diff should share parsed configs and succeed."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main([str(source_file), "--preset", "syntactic", "--verify", "--diff"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Fidelity Verification PASSED" in captured.err
    assert "Serialized configurations are semantically identical" in captured.err


def test_cli_error_writing_output(capsys):
    """CLI should return 1 when writing output file fails."""
    source_file = Path("configs/cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio")
    if not source_file.exists():
        pytest.skip(f"Config {source_file} not found")

    ret = main([str(source_file), "-o", "/non_existent_dir_xyz/out.ocio"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error writing output" in captured.err


def test_cli_main_module_execution():
    """Ensure ocio_minifier.cli can be invoked as __main__."""
    import runpy
    import sys

    old_argv = sys.argv
    try:
        sys.argv = ["ocio-minify", "--help"]
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("ocio_minifier.cli", run_name="__main__")
        assert exc.value.code == 0
    finally:
        sys.argv = old_argv
