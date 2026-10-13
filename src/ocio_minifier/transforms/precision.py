"""Floating-point precision rounding transformation."""

import re


class FloatPrecisionTransform:
    """Rounds floating point matrices to a target decimal precision."""

    name: str = "Float Precision Rounding (Lossy)"
    description: str = "Rounds excessive floating-point matrix data to 32-bit limits (e.g. 7 decimal places)"
    is_lossy: bool = True

    def __init__(self, decimals: int = 7):
        self.decimals = decimals

    def apply(self, content: str) -> str:
        # Match matrix arrays
        def _replace_matrix(match: re.Match[str]) -> str:
            prefix = match.group(1)
            raw_nums = match.group(2)
            # Find and round individual elements within the bracket
            tokens = raw_nums.split(",")
            cleaned_tokens = []
            for token in tokens:
                t_str = token.strip()
                if not t_str:
                    continue
                try:
                    val_f = float(t_str)
                    rounded = round(val_f, self.decimals)
                    if rounded.is_integer():
                        cleaned_tokens.append(str(int(rounded)))
                    else:
                        cleaned_tokens.append(f"{rounded:.{self.decimals}g}")
                except ValueError:
                    cleaned_tokens.append(t_str)
            cleaned_nums = ", ".join(cleaned_tokens)
            return f"{prefix}[{cleaned_nums}]"

        matrix_pattern = re.compile(
            r"([ \t]*matrix:\s*)\[([a-zA-Z0-9., \r\n\-eE]+)\]",
            re.MULTILINE,
        )
        return matrix_pattern.sub(_replace_matrix, content)


def transform_float_precision(text: str, decimals: int = 7) -> str:
    """Convenience function applying FloatPrecisionTransform."""
    return FloatPrecisionTransform(decimals=decimals).apply(text)
