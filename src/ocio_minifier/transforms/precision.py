"""Floating-point precision rounding transformation with invariant preservation."""

import re


class FloatPrecisionTransform:
    """Rounds floating point numbers to a target decimal precision while preserving mathematical invariants."""

    name: str = "Float Precision Rounding (Lossy)"
    description: str = (
        "Rounds excessive floating-point matrix data to target precision while "
        "preserving row sums, white point gain, and affine identity rows"
    )
    is_lossy: bool = True

    def __init__(
        self,
        decimals: int = 7,
        preserve_matrix_row_sums: bool = True,
        preserve_channel_symmetry: bool = True,
    ):
        self.decimals = decimals
        self.preserve_matrix_row_sums = preserve_matrix_row_sums
        self.preserve_channel_symmetry = preserve_channel_symmetry

    def _format_float(self, val: float) -> str:
        """Format rounded float compactly, stripping redundant trailing zeros."""
        val_rounded = round(val, self.decimals)
        if val_rounded.is_integer():
            return str(int(val_rounded))
        if 0 < abs(val_rounded) < 1e-4:
            return f"{val_rounded:.{self.decimals}g}"
        return f"{val_rounded:.{self.decimals}f}".rstrip("0").rstrip(".")

    def _process_matrix_16(self, raw_floats: list[float]) -> list[str]:
        """Process a 4x4 matrix preserving row sums, offsets, and affine bottom row."""
        results = [self._format_float(v) for v in raw_floats]
        floats = [round(v, self.decimals) for v in raw_floats]

        # 1. Row sum preservation for RGB rows 0, 1, 2
        if self.preserve_matrix_row_sums:
            for row_idx in range(3):
                idx0, idx1, idx2 = row_idx * 4, row_idx * 4 + 1, row_idx * 4 + 2
                unrounded_sum = raw_floats[idx0] + raw_floats[idx1] + raw_floats[idx2]

                target: float | None = None
                if abs(unrounded_sum - 1.0) < 1e-5:
                    target = 1.0
                elif abs(unrounded_sum - 0.0) < 1e-5:
                    target = 0.0

                if target is not None:
                    current_sum = floats[idx0] + floats[idx1] + floats[idx2]
                    residual = round(target - current_sum, self.decimals)
                    if residual != 0:
                        # Allocate residual to coefficient with largest absolute magnitude
                        row_indices = [idx0, idx1, idx2]
                        max_idx = max(row_indices, key=lambda k: abs(raw_floats[k]))
                        adjusted_val = round(floats[max_idx] + residual, self.decimals)
                        floats[max_idx] = adjusted_val
                        results[max_idx] = self._format_float(adjusted_val)

                # Snap near-zero translation offset to exact 0
                offset_idx = row_idx * 4 + 3
                if abs(raw_floats[offset_idx]) < 1e-7:
                    results[offset_idx] = "0"

        # 2. Affine bottom row invariant [0, 0, 0, 1]
        if (
            abs(raw_floats[12]) < 1e-7
            and abs(raw_floats[13]) < 1e-7
            and abs(raw_floats[14]) < 1e-7
            and abs(raw_floats[15] - 1.0) < 1e-5
        ):
            results[12] = "0"
            results[13] = "0"
            results[14] = "0"
            results[15] = "1"

        return results

    def _process_3_vector(self, raw_floats: list[float]) -> list[str]:
        """Process a 3-element vector (e.g. CDL slope/offset/power) preserving channel symmetry."""
        if (
            self.preserve_channel_symmetry
            and abs(raw_floats[0] - raw_floats[1]) < 1e-4
            and abs(raw_floats[1] - raw_floats[2]) < 1e-4
        ):
            avg = (raw_floats[0] + raw_floats[1] + raw_floats[2]) / 3.0
            formatted = self._format_float(avg)
            return [formatted, formatted, formatted]
        return [self._format_float(v) for v in raw_floats]

    def apply(self, content: str) -> str:
        def _replace_array(match: re.Match[str]) -> str:
            prefix = match.group(1)
            raw_nums = match.group(2)
            tokens = [x.strip() for x in raw_nums.split(",") if x.strip()]

            # Attempt parsing all tokens as floats
            float_vals: list[float] = []
            all_floats = True
            for t in tokens:
                try:
                    float_vals.append(float(t))
                except ValueError:
                    all_floats = False
                    break

            if all_floats:
                if len(float_vals) == 16 and "matrix" in prefix:
                    cleaned_tokens = self._process_matrix_16(float_vals)
                elif len(float_vals) == 3:
                    cleaned_tokens = self._process_3_vector(float_vals)
                else:
                    cleaned_tokens = [self._format_float(v) for v in float_vals]
            else:
                # Fallback: process individual valid float tokens, leaving non-floats as-is
                cleaned_tokens = []
                for t in tokens:
                    try:
                        val_f = float(t)
                        cleaned_tokens.append(self._format_float(val_f))
                    except ValueError:
                        cleaned_tokens.append(t)

            return f"{prefix}[{', '.join(cleaned_tokens)}]"

        array_pattern = re.compile(
            r"([ \t]*(?:matrix|slope|offset|power):\s*)\[([a-zA-Z0-9., \r\n\-eE]+)\]",
            re.MULTILINE,
        )
        return array_pattern.sub(_replace_array, content)


def transform_float_precision(
    text: str,
    decimals: int = 7,
    preserve_matrix_row_sums: bool = True,
    preserve_channel_symmetry: bool = True,
) -> str:
    """Convenience function applying FloatPrecisionTransform."""
    return FloatPrecisionTransform(
        decimals=decimals,
        preserve_matrix_row_sums=preserve_matrix_row_sums,
        preserve_channel_symmetry=preserve_channel_symmetry,
    ).apply(text)
