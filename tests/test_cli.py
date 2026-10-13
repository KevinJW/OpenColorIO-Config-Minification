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
    assert "Baseline (Unmodified)" in captured.out


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
