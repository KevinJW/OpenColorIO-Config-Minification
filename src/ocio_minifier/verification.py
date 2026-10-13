"""Mathematical DAG fidelity verification engine using PyOpenColorIO."""

import difflib
import math
from typing import Any

from ocio_minifier.models import ConversionFailure, VerificationResult

try:
    import PyOpenColorIO as ocio

    HAS_OCIO = True
except ImportError:
    ocio = None  # type: ignore[assignment]
    HAS_OCIO = False

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

    def diff_serialized(
        self,
        orig_cfg: Any,
        candidate_cfg: Any,
        from_label: str = "original_serialized.ocio",
        to_label: str = "minified_serialized.ocio",
    ) -> str:
        """Serialize both configs using PyOpenColorIO and return a unified diff."""
        return diff_serialized_configs(orig_cfg, candidate_cfg, from_label, to_label)

    def verify(self, orig_cfg: Any, candidate_cfg: Any) -> VerificationResult:
        """Evaluate pixel parity between orig_cfg and candidate_cfg."""
        if not HAS_OCIO or orig_cfg is None or candidate_cfg is None:
            return VerificationResult(
                passed=False,
                max_delta=0.0,
                tolerance=self.tolerance,
                failures=[
                    ConversionFailure(
                        target_type="System",
                        identifier="PyOpenColorIO",
                        input_rgb=(0.0, 0.0, 0.0),
                        error_message="PyOpenColorIO is not available or configuration is None",
                    )
                ],
            )

        max_delta = 0.0
        failures: list[ConversionFailure] = []
        evaluated_spaces = 0
        evaluated_views = 0

        # Determine reference space (scene_linear role or ACES2065-1 fallback)
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

        # 1. Evaluate forward (and optionally inverse) ColorSpace parity
        for cs in all_orig_cs:
            cs_name = cs.getName()
            evaluated_spaces += 1
            # Forward transform: ref -> cs
            try:
                proc_orig = orig_cfg.getProcessor(
                    ref_name, cs_name
                ).getDefaultCPUProcessor()
                proc_cand = candidate_cfg.getProcessor(
                    ref_name, cs_name
                ).getDefaultCPUProcessor()

                for rgb in self.pixel_grid:
                    out_orig = proc_orig.applyRGB(rgb)
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
                try:
                    proc_orig_inv = orig_cfg.getProcessor(
                        cs_name, ref_name
                    ).getDefaultCPUProcessor()
                    proc_cand_inv = candidate_cfg.getProcessor(
                        cs_name, ref_name
                    ).getDefaultCPUProcessor()

                    for rgb in self.pixel_grid:
                        out_orig = proc_orig_inv.applyRGB(rgb)
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
        for display in orig_cfg.getDisplays():
            for view in orig_cfg.getViews(display):
                evaluated_views += 1
                try:
                    proc_orig = orig_cfg.getProcessor(
                        ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                    ).getDefaultCPUProcessor()
                    proc_cand = candidate_cfg.getProcessor(
                        ref_name, display, view, ocio.TRANSFORM_DIR_FORWARD
                    ).getDefaultCPUProcessor()

                    for rgb in self.pixel_grid:
                        out_orig = proc_orig.applyRGB(rgb)
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
    if not HAS_OCIO or orig_cfg is None or candidate_cfg is None:
        raise ValueError(
            "PyOpenColorIO is required and both configurations must be non-None"
        )

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


def verify_dag_fidelity(
    orig_cfg: Any, min_cfg: Any, tol: float = 1e-6
) -> tuple[bool, float, list[str]]:
    """Legacy helper returning (passed, max_delta, failed_conversions)."""
    verifier = FidelityVerifier(tolerance=tol, check_inverse=False)
    result = verifier.verify(orig_cfg, min_cfg)
    return result.to_tuple()
