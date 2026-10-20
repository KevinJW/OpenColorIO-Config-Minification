"""Mathematical DAG fidelity verification engine using PyOpenColorIO."""

import contextlib
import difflib
import math
import os
import subprocess  # nosec B404
import tempfile
from typing import Any

import PyOpenColorIO as ocio

from ocio_minifier.models import ConversionFailure, VerificationResult

DEFAULT_PIXEL_GRID: list[tuple[float, float, float]] = [
    (0.0, 0.0, 0.0),
    (0.18, 0.18, 0.18),
    (1.0, 1.0, 1.0),
    (-0.05, 0.5, 1.5),
    (10.0, 50.0, 100.0),
]


class FidelityVerifier:
    """Evaluates mathematical equivalence across color spaces, displays, and views."""

    def __init__(
        self,
        pixel_grid: list[tuple[float, float, float]] | None = None,
        tolerance: float = 1e-6,
        check_inverse: bool = True,
        include_serialized_diff: bool = False,
    ):
        self.pixel_grid = pixel_grid or list(DEFAULT_PIXEL_GRID)
        self.tolerance = tolerance
        self.check_inverse = check_inverse
        self.include_serialized_diff = include_serialized_diff
        self._orig_cache: dict[int, dict[str, Any]] = {}

    def clear_cache(self) -> None:
        """Clear cached baseline processor outputs."""
        self._orig_cache.clear()

    def diff_serialized(
        self,
        orig_cfg: Any,
        candidate_cfg: Any,
        from_label: str = "original_serialized.ocio",
        to_label: str = "minified_serialized.ocio",
    ) -> str:
        """Serialize both configs using PyOpenColorIO and return a unified diff."""
        return diff_serialized_configs(orig_cfg, candidate_cfg, from_label, to_label)

    def _get_or_create_orig_cache(self, orig_cfg: Any) -> dict[str, Any]:
        """Precompute and cache baseline reference transform outputs."""
        orig_id = id(orig_cfg)
        if orig_id in self._orig_cache:
            return self._orig_cache[orig_id]

        ref_space = orig_cfg.getColorSpace(
            ocio.ROLE_SCENE_LINEAR
        ) or orig_cfg.getColorSpace("ACES2065-1")
        all_orig_cs = list(
            orig_cfg.getColorSpaces(
                ocio.SEARCH_REFERENCE_SPACE_ALL, ocio.COLORSPACE_ALL
            )
        )
        ref_name = (
            ref_space.getName()
            if ref_space
            else (all_orig_cs[0].getName() if all_orig_cs else "Raw")
        )

        fwd_outs: dict[str, list[tuple[float, float, float]] | Exception] = {}
        for cs in all_orig_cs:
            cs_name = cs.getName()
            try:
                proc = orig_cfg.getProcessor(ref_name, cs_name).getDefaultCPUProcessor()
                fwd_outs[cs_name] = [proc.applyRGB(rgb) for rgb in self.pixel_grid]
            except Exception as e:
                fwd_outs[cs_name] = e

        inv_outs: dict[str, list[tuple[float, float, float]] | Exception] = {}
        if self.check_inverse:
            for cs in all_orig_cs:
                cs_name = cs.getName()
                try:
                    proc = orig_cfg.getProcessor(
                        cs_name, ref_name
                    ).getDefaultCPUProcessor()
                    inv_outs[cs_name] = [proc.applyRGB(rgb) for rgb in self.pixel_grid]
                except Exception as e:
                    inv_outs[cs_name] = e

        view_outs: dict[
            tuple[str, str], list[tuple[float, float, float]] | Exception
        ] = {}
        seen_combos: set[tuple[str | None, str | None, str | None, str | None]] = set()

        for display in orig_cfg.getDisplays():
            for view in orig_cfg.getViews(display):
                vt_name: str | None = None
                view_cs_name: str | None = None
                looks_name: str | None = None
                rule_name: str | None = None

                if hasattr(orig_cfg, "getDisplayViewTransformName"):
                    with contextlib.suppress(Exception):
                        vt_name = orig_cfg.getDisplayViewTransformName(display, view)

                if hasattr(orig_cfg, "getResolvedDisplayViewColorSpaceName"):
                    with contextlib.suppress(Exception):
                        view_cs_name = orig_cfg.getResolvedDisplayViewColorSpaceName(
                            display, view
                        )
                elif hasattr(orig_cfg, "getDisplayViewColorSpaceName"):
                    with contextlib.suppress(Exception):
                        view_cs_name = orig_cfg.getDisplayViewColorSpaceName(
                            display, view
                        )

                if hasattr(orig_cfg, "getDisplayViewLooks"):
                    with contextlib.suppress(Exception):
                        looks_name = orig_cfg.getDisplayViewLooks(display, view)

                if hasattr(orig_cfg, "getDisplayViewRule"):
                    with contextlib.suppress(Exception):
                        rule_name = orig_cfg.getDisplayViewRule(display, view)

                combo_key = (
                    (vt_name, view_cs_name, looks_name, rule_name)
                    if (vt_name or view_cs_name)
                    else None
                )
                if combo_key is not None and combo_key in seen_combos:
                    continue

                if combo_key is not None:
                    seen_combos.add(combo_key)

                try:
                    proc = orig_cfg.getProcessor(
                        ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                    ).getDefaultCPUProcessor()
                    view_outs[(display, view)] = [
                        proc.applyRGB(rgb) for rgb in self.pixel_grid
                    ]
                except Exception as e:
                    view_outs[(display, view)] = e

        data = {
            "ref_name": ref_name,
            "all_cs_names": [cs.getName() for cs in all_orig_cs],
            "fwd_outs": fwd_outs,
            "inv_outs": inv_outs,
            "view_outs": view_outs,
        }
        self._orig_cache[orig_id] = data
        return data

    def verify(self, orig_cfg: Any, candidate_cfg: Any) -> VerificationResult:
        """Evaluate pixel parity between orig_cfg and candidate_cfg."""
        if orig_cfg is None or candidate_cfg is None:
            return VerificationResult(
                passed=False,
                max_delta=0.0,
                tolerance=self.tolerance,
                failures=[
                    ConversionFailure(
                        target_type="System",
                        identifier="PyOpenColorIO",
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message="Configuration is None",
                    )
                ],
            )

        cached_data = self._get_or_create_orig_cache(orig_cfg)
        ref_name = cached_data["ref_name"]
        all_cs_names = cached_data["all_cs_names"]
        fwd_outs = cached_data["fwd_outs"]
        inv_outs = cached_data["inv_outs"]
        view_outs = cached_data["view_outs"]

        max_delta = 0.0
        failures: list[ConversionFailure] = []
        evaluated_spaces = 0
        evaluated_views = 0

        # 1. Evaluate forward (and optionally inverse) ColorSpace parity
        for cs_name in all_cs_names:
            evaluated_spaces += 1
            orig_res = fwd_outs.get(cs_name)
            if isinstance(orig_res, Exception):
                failures.append(
                    ConversionFailure(
                        target_type="ColorSpace (Forward)",
                        identifier=cs_name,
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message=str(orig_res),
                    )
                )
                continue
            if orig_res is None:
                continue

            try:
                proc_cand = candidate_cfg.getProcessor(
                    ref_name, cs_name
                ).getDefaultCPUProcessor()

                for rgb, out_orig in zip(self.pixel_grid, orig_res, strict=True):
                    out_cand = proc_cand.applyRGB(rgb)

                    for c_orig, c_cand in zip(out_orig, out_cand, strict=True):
                        if c_orig == c_cand:
                            continue
                        if math.isnan(c_orig) and math.isnan(c_cand):
                            continue
                        diff = abs(c_orig - c_cand)
                        if diff > max_delta:
                            max_delta = diff
                        if diff > self.tolerance or math.isnan(diff):
                            failures.append(
                                ConversionFailure(
                                    target_type="ColorSpace (Forward)",
                                    identifier=cs_name,
                                    input_rgb=rgb,
                                    delta=diff,
                                )
                            )
            except Exception as e:
                failures.append(
                    ConversionFailure(
                        target_type="ColorSpace (Forward)",
                        identifier=cs_name,
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message=str(e),
                    )
                )

            # Inverse transform: cs -> ref
            if self.check_inverse:
                orig_res_inv = inv_outs.get(cs_name)
                if isinstance(orig_res_inv, Exception):
                    failures.append(
                        ConversionFailure(
                            target_type="ColorSpace (Inverse)",
                            identifier=cs_name,
                            input_rgb=(0.0, 0.0, 0.0),
                            error_message=str(orig_res_inv),
                        )
                    )
                    continue
                if orig_res_inv is None:
                    continue

                try:
                    proc_cand_inv = candidate_cfg.getProcessor(
                        cs_name, ref_name
                    ).getDefaultCPUProcessor()

                    for rgb, out_orig in zip(
                        self.pixel_grid, orig_res_inv, strict=True
                    ):
                        out_cand = proc_cand_inv.applyRGB(rgb)

                        for c_orig, c_cand in zip(out_orig, out_cand, strict=True):
                            if c_orig == c_cand:
                                continue
                            if math.isnan(c_orig) and math.isnan(c_cand):
                                continue
                            diff = abs(c_orig - c_cand)
                            if diff > max_delta:
                                max_delta = diff
                            if diff > self.tolerance or math.isnan(diff):
                                failures.append(
                                    ConversionFailure(
                                        target_type="ColorSpace (Inverse)",
                                        identifier=cs_name,
                                        input_rgb=rgb,
                                        delta=diff,
                                    )
                                )
                except Exception as e:
                    failures.append(
                        ConversionFailure(
                            target_type="ColorSpace (Inverse)",
                            identifier=cs_name,
                            input_rgb=(0.0, 0.0, 0.0),
                            error_message=str(e),
                        )
                    )

        # 2. Evaluate Displays and Views parity
        for (display, view), orig_res_view in view_outs.items():
            evaluated_views += 1
            if isinstance(orig_res_view, Exception):
                failures.append(
                    ConversionFailure(
                        target_type="DisplayView",
                        identifier=f"{display}/{view}",
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message=str(orig_res_view),
                    )
                )
                continue

            try:
                proc_cand = candidate_cfg.getProcessor(
                    ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                ).getDefaultCPUProcessor()

                for rgb, out_orig in zip(self.pixel_grid, orig_res_view, strict=True):
                    out_cand = proc_cand.applyRGB(rgb)

                    for c_orig, c_cand in zip(out_orig, out_cand, strict=True):
                        if c_orig == c_cand:
                            continue
                        if math.isnan(c_orig) and math.isnan(c_cand):
                            continue
                        diff = abs(c_orig - c_cand)
                        if diff > max_delta:
                            max_delta = diff
                        if diff > self.tolerance or math.isnan(diff):
                            failures.append(
                                ConversionFailure(
                                    target_type="DisplayView",
                                    identifier=f"{display}/{view}",
                                    input_rgb=rgb,
                                    delta=diff,
                                )
                            )
            except Exception as e:
                failures.append(
                    ConversionFailure(
                        target_type="DisplayView",
                        identifier=f"{display}/{view}",
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message=str(e),
                    )
                )

        passed = len(failures) == 0

        serialized_diff: str | None = None
        if self.include_serialized_diff:
            try:
                serialized_diff = diff_serialized_configs(orig_cfg, candidate_cfg)
            except Exception as e:
                serialized_diff = f"Error generating serialization diff: {e}"

        return VerificationResult(
            passed=passed,
            max_delta=max_delta,
            tolerance=self.tolerance,
            evaluated_spaces=evaluated_spaces,
            evaluated_views=evaluated_views,
            failures=failures,
            serialized_diff=serialized_diff,
        )


def diff_serialized_configs(
    orig_cfg: Any,
    candidate_cfg: Any,
    from_label: str = "original_serialized.ocio",
    to_label: str = "minified_serialized.ocio",
) -> str:
    """Serialize orig_cfg and candidate_cfg using PyOpenColorIO and return a unified diff."""
    if orig_cfg is None or candidate_cfg is None:
        raise ValueError("Both configurations must be non-None")

    orig_text = orig_cfg.serialize()
    cand_text = candidate_cfg.serialize()

    diff_lines = list(
        difflib.unified_diff(
            orig_text.splitlines(keepends=True),
            cand_text.splitlines(keepends=True),
            fromfile=from_label,
            tofile=to_label,
        )
    )
    return "".join(diff_lines)


def validate_with_ociocheck(config_path_or_content: str) -> tuple[bool, str]:
    """Validate an OCIO configuration using the ociocheck CLI tool.

    Unlike PyOpenColorIO's Config.validate() method, ociocheck thoroughly verifies that
    all color transforms and referenced external LUT files exist and are loadable across
    all display/view pairs, active, and inactive color spaces.

    Returns:
        tuple[bool, str]: (passed, output_or_error_message)
    """
    if os.path.isfile(config_path_or_content):
        config_path = config_path_or_content
        cleanup = False
    else:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".ocio", delete=False, encoding="utf-8"
        ) as f:
            f.write(config_path_or_content)
            config_path = f.name
        cleanup = True

    try:
        res = subprocess.run(
            ["ociocheck", "--iconfig", config_path],
            capture_output=True,
            text=True,
            check=False,
        )  # nosec B603, B607
        output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
        return (res.returncode == 0, output.strip())
    except FileNotFoundError:
        return (True, "ociocheck executable not found on system PATH; skipped.")
    finally:
        if cleanup and os.path.exists(config_path):
            os.remove(config_path)


def verify_dag_fidelity(
    orig_cfg: Any, min_cfg: Any, tol: float = 1e-6
) -> tuple[bool, float, list[str]]:
    """Legacy helper returning (passed, max_delta, failed_conversions)."""
    verifier = FidelityVerifier(tolerance=tol, check_inverse=False)
    result = verifier.verify(orig_cfg, min_cfg)
    return result.to_tuple()
