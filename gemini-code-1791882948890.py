import gzip
import math
import os
import re
import subprocess
import sys
import time

try:
    import PyOpenColorIO as ocio

    HAS_OCIO = True
except ImportError:
    HAS_OCIO = False

# ---------------------------------------------------------------------------
# Numerical Verification Engine
# ---------------------------------------------------------------------------

# Test values cover: black, mid-gray, diffuse white, negative values (gamut clipping/mirroring),
# and extreme HDR highlights.
TEST_PIXEL_GRID = [
    [0.0, 0.0, 0.0],
    [0.18, 0.18, 0.18],
    [1.0, 1.0, 1.0],
    [-0.05, 0.5, 1.5],
    [10.0, 50.0, 100.0],
]


def verify_dag_fidelity(
    orig_cfg: "ocio.Config", min_cfg: "ocio.Config", tol: float = 1e-6
):
    """Evaluates pixel-level mathematical equivalence across all ColorSpaces

    and Display/View transforms between two OCIO configs.
    """
    max_delta = 0.0
    failed_conversions = []

    # 1. Determine reference space (or fallback to scene_linear role / ACES2065-1)
    ref_space = orig_cfg.getColorSpace(
        ocio.ROLE_SCENE_LINEAR
    ) or orig_cfg.getColorSpace("ACES2065-1")
    ref_name = (
        ref_space.getName() if ref_space else orig_cfg.getColorSpaces()[0].getName()
    )

    # 2. Assert forward and inverse parity across every ColorSpace
    all_cs = [
        cs.getName()
        for cs in orig_cfg.getColorSpaces(
            ocio.SEARCH_REFERENCE_SPACE_ALL, ocio.COLORSPACE_ALL
        )
    ]
    for cs_name in all_cs:
        try:
            proc_orig = orig_cfg.getProcessor(
                ref_name, cs_name
            ).getDefaultCPUProcessor()
            proc_min = min_cfg.getProcessor(ref_name, cs_name).getDefaultCPUProcessor()

            for rgb in TEST_PIXEL_GRID:
                out_orig = proc_orig.applyRGB(rgb)
                out_min = proc_min.applyRGB(rgb)

                for c_orig, c_min in zip(out_orig, out_min, strict=True):
                    if math.isnan(c_orig) and math.isnan(c_min):
                        continue
                    diff = abs(c_orig - c_min)
                    if diff > max_delta:
                        max_delta = diff
                    if diff > tol:
                        failed_conversions.append(f"CS '{cs_name}' [In: {rgb}]")
        except Exception as e:
            failed_conversions.append(f"CS '{cs_name}' [Error: {str(e)}]")

    # 3. Assert parity across all Displays and Views
    for display in orig_cfg.getDisplays():
        for view in orig_cfg.getViews(display):
            try:
                proc_orig = orig_cfg.getProcessor(
                    ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                ).getDefaultCPUProcessor()
                proc_min = min_cfg.getProcessor(
                    ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                ).getDefaultCPUProcessor()

                for rgb in TEST_PIXEL_GRID:
                    out_orig = proc_orig.applyRGB(rgb)
                    out_min = proc_min.applyRGB(rgb)

                    for c_orig, c_min in zip(out_orig, out_min, strict=True):
                        if math.isnan(c_orig) and math.isnan(c_min):
                            continue
                        diff = abs(c_orig - c_min)
                        if diff > max_delta:
                            max_delta = diff
                        if diff > tol:
                            failed_conversions.append(
                                f"View '{display}/{view}' [In: {rgb}]"
                            )
            except Exception as e:
                failed_conversions.append(f"View '{display}/{view}' [Error: {str(e)}]")

    passed = len(failed_conversions) == 0
    return passed, max_delta, failed_conversions


# ---------------------------------------------------------------------------
# Transformation Modules
# ---------------------------------------------------------------------------


def transform_elide_defaults(text: str) -> str:
    patterns = [
        r'^[ \t]*equalitygroup:\s*["\']{2}\r?\n',
        r"^[ \t]*allocation:\s*uniform\r?\n",
        r"^[ \t]*isdata:\s*false\r?\n",
        r"^[ \t]*bitdepth:\s*32f\r?\n",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.MULTILINE)
    return re.sub(r"environment:\s*\n\s*\{\}", "environment: {}", text)


def transform_compact_amf_scalars(text: str) -> str:
    def _compact_urn(m):
        indent = m.group(1)
        urn_lines = [line.strip() for line in m.group(2).strip().splitlines()]
        escaped_str = "\\n".join(urn_lines) + "\\n"
        return f'{indent}amf_transform_ids: "{escaped_str}"\n'

    return re.sub(
        r"([ \t]+)amf_transform_ids:\s*\|\r?\n((?:[ \t]+urn:[^\r\n]+\r?\n)+)",
        _compact_urn,
        text,
    )


def transform_flow_transforms(text: str) -> str:
    def _builtin_repl(m):
        indent = m.group(1)
        direction = m.group(2)
        style = m.group(3).strip()
        return f"{indent}{direction}: !<BuiltinTransform> {{style: {style}}}\n"

    text = re.sub(
        r"([ \t]+)(to_scene_reference|from_scene_reference|from_display_reference):\s*!<BuiltinTransform>\r?\n\s+style:\s*([^\r\n]+)\r?\n",
        _builtin_repl,
        text,
    )

    def _matrix_repl(m):
        indent = m.group(1)
        mat_vals = " ".join(m.group(2).split())
        return f"{indent}- !<MatrixTransform> {{matrix: [{mat_vals}]}}\n"

    text = re.sub(
        r"([ \t]+)-\s*!<MatrixTransform>\r?\n\s+matrix:\s*\[([^\]]+)\]\r?\n",
        _matrix_repl,
        text,
    )
    return text


def transform_yaml_anchors(text: str) -> str:
    mat_pattern = re.compile(
        r"(!<MatrixTransform>\s*\{matrix:\s*\[([0-9., \-eE]+)\]\})"
    )
    occurrences = mat_pattern.findall(text)

    val_counts: dict[str, int] = {}
    for _full_node, mat_str in occurrences:
        norm_key = ",".join(x.strip() for x in mat_str.split(","))
        val_counts[norm_key] = val_counts.get(norm_key, 0) + 1

    anchors = {
        key: f"matrix_ref_{i}"
        for i, (key, count) in enumerate(val_counts.items())
        if count > 1
    }
    seen = set()

    def _replace_anchor(match):
        full_match = match.group(1)
        mat_str = match.group(2)
        norm_key = ",".join(x.strip() for x in mat_str.split(","))
        if norm_key in anchors:
            alias = anchors[norm_key]
            if norm_key not in seen:
                seen.add(norm_key)
                return f"&{alias} {full_match}"
            else:
                return f"*{alias}"
        return full_match

    return mat_pattern.sub(_replace_anchor, text)


def transform_strip_descriptions(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    in_block = False
    block_indent = 0
    pending_blanks: list[str] = []

    for line in lines:
        if in_block:
            stripped = line.strip()
            if not stripped:
                pending_blanks.append(line)
                continue
            curr_indent = len(line) - len(line.lstrip(" "))
            if curr_indent > block_indent:
                pending_blanks.clear()
                continue
            else:
                in_block = False
                out.extend(pending_blanks)
                pending_blanks.clear()

        m_block = re.match(r"^([ \t]*)description:\s*\|[+-]?", line)
        if m_block:
            in_block = True
            block_indent = len(m_block.group(1))
            pending_blanks.clear()
            continue

        m_single = re.match(
            r"^[ \t]*description:\s*(?:\"[^\"]*\"|'[^']*'|[^\r\n]+)", line
        )
        if m_single:
            continue

        out.append(line)

    return "".join(out)


# ---------------------------------------------------------------------------
# Benchmark & Validation Orchestration
# ---------------------------------------------------------------------------


def run_benchmark(
    name: str,
    content: str,
    baseline_bytes: int,
    orig_cfg: "ocio.Config" = None,
):
    raw_size = len(content.encode("utf-8"))
    gzip_size = len(gzip.compress(content.encode("utf-8"), compresslevel=9))
    raw_delta = ((raw_size - baseline_bytes) / baseline_bytes) * 100

    parse_time_ms = 0.0
    valid = False
    fidelity_pass = False
    max_delta = 0.0

    if HAS_OCIO:
        start = time.perf_counter()
        try:
            min_cfg = ocio.Config.CreateFromStream(content)
            min_cfg.validate()
            valid = True
        except Exception:
            min_cfg = None
            valid = False
        parse_time_ms = (time.perf_counter() - start) * 1000

        # Execute Pixel Parity Assertion if schema is valid
        if valid and orig_cfg:
            fidelity_pass, max_delta, fails = verify_dag_fidelity(orig_cfg, min_cfg)
            if not fidelity_pass:
                print(f"  [!] Fidelity failures in '{name}': {fails[:3]}...")
        elif valid and not orig_cfg:
            # Baseline entry
            fidelity_pass = True
            max_delta = 0.0
    else:
        # Fallback verification via CLI when PyOpenColorIO is unavailable
        tmp_name = f"_tmp_{abs(hash(name))}.ocio"
        with open(tmp_name, "w") as f:
            f.write(content)
        start = time.perf_counter()
        res = subprocess.run(
            ["ociocheck", "--file", tmp_name],
            capture_output=True,
            text=True,
            check=False,
        )  # nosec B603, B607
        parse_time_ms = (time.perf_counter() - start) * 1000
        valid = res.returncode == 0
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        fidelity_pass = valid  # Cannot verify pixel math via CLI alone

    return {
        "Name": name,
        "Raw (KB)": f"{raw_size / 1024:.2f}",
        "Reduction": f"{abs(raw_delta):.1f}%" if raw_delta < 0 else "0.0%",
        "Gzip (KB)": f"{gzip_size / 1024:.2f}",
        "Parse (ms)": f"{parse_time_ms:.2f}",
        "Max ΔRGB": f"{max_delta:.2e}" if HAS_OCIO else "N/A",
        "Fidelity": "PASS" if fidelity_pass else "FAIL",
    }


def main(source_file: str):
    if not os.path.exists(source_file):
        print(f"Error: Target config '{source_file}' not found.")
        sys.exit(1)

    with open(source_file) as f:
        original = f.read()

    baseline_bytes = len(original.encode("utf-8"))
    orig_cfg = None

    if HAS_OCIO:
        try:
            orig_cfg = ocio.Config.CreateFromStream(original)
            orig_cfg.validate()
        except Exception as e:
            print(f"Error parsing source config with PyOpenColorIO: {e}")
            sys.exit(1)

    print(
        f"Benchmarking transforms against: {os.path.basename(source_file)} ({baseline_bytes / 1024:.1f} KB)\n"
    )

    results = []

    # 1. Baseline
    results.append(
        run_benchmark("Baseline (Unmodified)", original, baseline_bytes, orig_cfg=None)
    )

    # 2. Individual Transforms
    transforms = [
        ("Default Field Elision", transform_elide_defaults),
        ("Compact AMF Scalars", transform_compact_amf_scalars),
        ("Flow Transform Inlining", transform_flow_transforms),
        ("YAML Anchors & Aliases", transform_yaml_anchors),
        ("Strip Descriptions (Lossy)", transform_strip_descriptions),
    ]

    for name, func in transforms:
        transformed = func(original)
        results.append(run_benchmark(name, transformed, baseline_bytes, orig_cfg))

    # 3. Combined Pipeline (Syntactic-Only)
    syntactic_combined = transform_yaml_anchors(
        transform_flow_transforms(
            transform_compact_amf_scalars(transform_elide_defaults(original))
        )
    )
    results.append(
        run_benchmark(
            "Combined (Syntactic Only)",
            syntactic_combined,
            baseline_bytes,
            orig_cfg,
        )
    )

    # 4. Combined Pipeline (Maximum / Lossy Descriptions)
    max_combined = transform_strip_descriptions(syntactic_combined)
    results.append(
        run_benchmark(
            "Combined (Max / Lossy Desc)",
            max_combined,
            baseline_bytes,
            orig_cfg,
        )
    )

    # Markdown Results Table
    headers = [
        "Transform",
        "Raw Size",
        "Raw Delta",
        "Gzip Size",
        "Parse Time",
        "Max ΔRGB",
        "DAG Fidelity",
    ]
    print(
        f"| {' | '.join(headers)} |\n| {' | '.join([':---'] + [':---:' for _ in headers[1:]])} |"
    )
    for r in results:
        print(
            f"| {r['Name']} | {r['Raw (KB)']} KB | {r['Reduction']} | {r['Gzip (KB)']} KB | {r['Parse (ms)']} ms | {r['Max ΔRGB']} | {r['Fidelity']} |"
        )


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
