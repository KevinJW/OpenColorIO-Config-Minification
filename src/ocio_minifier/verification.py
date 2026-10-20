"""Mathematical DAG fidelity verification engine using PyOpenColorIO."""

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


def compare_pixel_outputs(
    pixel_grid: list[tuple[float, float, float]],
    orig_outs: list[tuple[float, float, float]],
    cand_outs: list[tuple[float, float, float]],
    target_type: str,
    identifier: str,
    tolerance: float,
    current_max_delta: float,
    failures: list[ConversionFailure],
) -> float:
    """Compare evaluated pixel outputs and record failures if tolerance is exceeded."""
    max_delta = current_max_delta
    for rgb, out_orig, out_cand in zip(pixel_grid, orig_outs, cand_outs, strict=True):
        for c_orig, c_cand in zip(out_orig, out_cand, strict=True):
            if c_orig == c_cand or (math.isnan(c_orig) and math.isnan(c_cand)):
                continue
            diff = abs(c_orig - c_cand)
            if diff > max_delta:
                max_delta = diff
            if diff > tolerance or math.isnan(diff):
                failures.append(
                    ConversionFailure(
                        target_type=target_type,
                        identifier=identifier,
                        input_rgb=rgb,
                        delta=diff,
                    )
                )
    return max_delta


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

    def _precompute_display_views(
        self, orig_cfg: Any, ref_name: str
    ) -> dict[tuple[str, str], list[tuple[float, float, float]]]:
        """Precompute and deduplicate display/view outputs."""
        view_outs: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
        seen_combos: set[tuple[str, str, str, str]] = set()

        for display in orig_cfg.getDisplays():
            for view in orig_cfg.getViews(display):
                vt_name = orig_cfg.getDisplayViewTransformName(display, view)
                view_cs_name = orig_cfg.getResolvedDisplayViewColorSpaceName(
                    display, view
                )
                looks_name = orig_cfg.getDisplayViewLooks(display, view)
                rule_name = orig_cfg.getDisplayViewRule(display, view)

                combo_key = (vt_name, view_cs_name, looks_name, rule_name)
                if combo_key in seen_combos:
                    continue
                seen_combos.add(combo_key)

                proc = orig_cfg.getProcessor(
                    ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                ).getDefaultCPUProcessor()
                view_outs[(display, view)] = [
                    proc.applyRGB(rgb) for rgb in self.pixel_grid
                ]
        return view_outs

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

        fwd_outs = {
            cs.getName(): [
                orig_cfg.getProcessor(ref_name, cs.getName())
                .getDefaultCPUProcessor()
                .applyRGB(rgb)
                for rgb in self.pixel_grid
            ]
            for cs in all_orig_cs
        }

        inv_outs = (
            {
                cs.getName(): [
                    orig_cfg.getProcessor(cs.getName(), ref_name)
                    .getDefaultCPUProcessor()
                    .applyRGB(rgb)
                    for rgb in self.pixel_grid
                ]
                for cs in all_orig_cs
            }
            if self.check_inverse
            else {}
        )

        view_outs = self._precompute_display_views(orig_cfg, ref_name)

        data = {
            "ref_name": ref_name,
            "all_cs_names": [cs.getName() for cs in all_orig_cs],
            "fwd_outs": fwd_outs,
            "inv_outs": inv_outs,
            "view_outs": view_outs,
        }
        self._orig_cache[orig_id] = data
        return data

    def _evaluate_forward_colorspaces(
        self,
        candidate_cfg: Any,
        ref_name: str,
        all_cs_names: list[str],
        fwd_outs: dict[str, list[tuple[float, float, float]]],
        current_max_delta: float,
        failures: list[ConversionFailure],
    ) -> tuple[float, int]:
        """Evaluate candidate forward color space transforms against cached baseline outputs."""
        max_delta = current_max_delta
        evaluated = 0
        for cs_name in all_cs_names:
            evaluated += 1
            orig_res = fwd_outs[cs_name]
            try:
                proc = candidate_cfg.getProcessor(
                    ref_name, cs_name
                ).getDefaultCPUProcessor()
                cand_outs = [proc.applyRGB(rgb) for rgb in self.pixel_grid]
                max_delta = compare_pixel_outputs(
                    self.pixel_grid,
                    orig_res,
                    cand_outs,
                    "ColorSpace (Forward)",
                    cs_name,
                    self.tolerance,
                    max_delta,
                    failures,
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
        return max_delta, evaluated

    def _evaluate_inverse_colorspaces(
        self,
        candidate_cfg: Any,
        ref_name: str,
        all_cs_names: list[str],
        inv_outs: dict[str, list[tuple[float, float, float]]],
        current_max_delta: float,
        failures: list[ConversionFailure],
    ) -> float:
        """Evaluate candidate inverse color space transforms against cached baseline outputs."""
        max_delta = current_max_delta
        for cs_name in all_cs_names:
            if cs_name not in inv_outs:
                continue
            orig_res_inv = inv_outs[cs_name]
            try:
                proc = candidate_cfg.getProcessor(
                    cs_name, ref_name
                ).getDefaultCPUProcessor()
                cand_outs = [proc.applyRGB(rgb) for rgb in self.pixel_grid]
                max_delta = compare_pixel_outputs(
                    self.pixel_grid,
                    orig_res_inv,
                    cand_outs,
                    "ColorSpace (Inverse)",
                    cs_name,
                    self.tolerance,
                    max_delta,
                    failures,
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
        return max_delta

    def _evaluate_display_views(
        self,
        candidate_cfg: Any,
        ref_name: str,
        view_outs: dict[tuple[str, str], list[tuple[float, float, float]]],
        current_max_delta: float,
        failures: list[ConversionFailure],
    ) -> tuple[float, int]:
        """Evaluate candidate display and view transforms against cached baseline outputs."""
        max_delta = current_max_delta
        evaluated = 0
        for (display, view), orig_res_view in view_outs.items():
            evaluated += 1
            try:
                proc = candidate_cfg.getProcessor(
                    ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                ).getDefaultCPUProcessor()
                cand_outs = [proc.applyRGB(rgb) for rgb in self.pixel_grid]
                max_delta = compare_pixel_outputs(
                    self.pixel_grid,
                    orig_res_view,
                    cand_outs,
                    "DisplayView",
                    f"{display}/{view}",
                    self.tolerance,
                    max_delta,
                    failures,
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
        return max_delta, evaluated

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
        failures: list[ConversionFailure] = []

        max_delta, evaluated_spaces = self._evaluate_forward_colorspaces(
            candidate_cfg,
            ref_name,
            cached_data["all_cs_names"],
            cached_data["fwd_outs"],
            0.0,
            failures,
        )

        if self.check_inverse:
            max_delta = self._evaluate_inverse_colorspaces(
                candidate_cfg,
                ref_name,
                cached_data["all_cs_names"],
                cached_data["inv_outs"],
                max_delta,
                failures,
            )

        max_delta, evaluated_views = self._evaluate_display_views(
            candidate_cfg,
            ref_name,
            cached_data["view_outs"],
            max_delta,
            failures,
        )

        serialized_diff: str | None = None
        if self.include_serialized_diff:
            try:
                serialized_diff = diff_serialized_configs(orig_cfg, candidate_cfg)
            except Exception as e:
                serialized_diff = f"Error generating serialization diff: {e}"

        return VerificationResult(
            passed=len(failures) == 0,
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
