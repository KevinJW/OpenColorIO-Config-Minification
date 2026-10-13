"""Flow mapping inlining transformation for BuiltinTransform and MatrixTransform."""

import re


class FlowTransformsTransform:
    """Inlines BuiltinTransforms and list MatrixTransforms into compact flow mapping syntax."""

    name: str = "Flow Transform Inlining"
    description: str = "Inlines BuiltinTransforms and list-based MatrixTransforms into single-line flow mappings"
    is_lossy: bool = False

    def apply(self, content: str) -> str:
        # 1. Inline BuiltinTransforms
        builtin_pattern = re.compile(
            r"^([ \t]*(?:to_scene_reference|from_scene_reference|from_display_reference):\s*!<BuiltinTransform>)\r?\n[ \t]*style:\s*([^\r\n]+)",
            re.MULTILINE,
        )
        content = builtin_pattern.sub(r"\1 {style: \2}", content)

        # 2. Inline MatrixTransforms in sequence lists
        matrix_pattern = re.compile(
            r"^([ \t]*-[ \t]*!<MatrixTransform>)\r?\n[ \t]*matrix:\s*\[([0-9., \r\n\-eE]+)\]",
            re.MULTILINE,
        )

        def _clean_matrix(match: re.Match) -> str:
            prefix = match.group(1)
            raw_nums = match.group(2)
            cleaned_nums = ", ".join(
                x.strip() for x in raw_nums.split(",") if x.strip()
            )
            return f"{prefix} {{matrix: [{cleaned_nums}]}}"

        return matrix_pattern.sub(_clean_matrix, content)


def transform_flow_transforms(text: str) -> str:
    """Convenience function applying FlowTransformsTransform."""
    return FlowTransformsTransform().apply(text)
