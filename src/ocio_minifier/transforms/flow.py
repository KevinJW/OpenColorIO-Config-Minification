"""Flow mapping and sequence inlining transformations for OCIO structures."""

import re


class FlowTransformsTransform:
    """Inlines Builtin, Matrix, CDL, File, and ColorSpace transforms, roles, and group children into flow syntax."""

    name: str = "Flow Transform Inlining"
    description: str = (
        "Inlines BuiltinTransforms, list MatrixTransforms, FileTransforms, "
        "ColorSpaceTransforms, roles dictionary, and GroupTransform children into compact flow syntax"
    )
    is_lossy: bool = False

    def _inline_builtins(self, content: str) -> str:
        builtin_pattern = re.compile(
            r"^([ \t]*(?:to_scene_reference|from_scene_reference|from_display_reference):\s*!<BuiltinTransform>)\r?\n[ \t]*style:\s*([^\r\n]+)",
            re.MULTILINE,
        )
        return builtin_pattern.sub(r"\1 {style: \2}", content)

    def _inline_matrix_lists(self, content: str) -> str:
        matrix_pattern = re.compile(
            r"^([ \t]*-[ \t]*!<MatrixTransform>)\r?\n[ \t]*matrix:\s*\[([0-9., \r\n\-eE]+)\]",
            re.MULTILINE,
        )

        def _clean_matrix(match: re.Match[str]) -> str:
            prefix = match.group(1)
            raw_nums = match.group(2)
            cleaned_nums = ", ".join(
                x.strip() for x in raw_nums.split(",") if x.strip()
            )
            return f"{prefix} {{matrix: [{cleaned_nums}]}}"

        return matrix_pattern.sub(_clean_matrix, content)

    def _inline_roles(self, content: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            prefix = m.group(1)
            pairs = [
                s
                for line in m.group(2).splitlines()
                if (s := line.strip()) and ":" in s and not s.startswith("#")
            ]
            return f"{prefix} {{{', '.join(pairs)}}}\n"

        pattern = re.compile(
            r"^(roles:)\r?\n((?:[ \t]+[a-zA-Z0-9_\-]+:\s*[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return pattern.sub(_repl, content)

    def _inline_group_children(self, content: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            prefix = m.group(1)
            items = [
                s[2:].strip()
                for line in m.group(2).splitlines()
                if (s := line.strip()).startswith("- ")
            ]
            return f"{prefix} [{', '.join(items)}]\n"

        pattern = re.compile(
            r"^([ \t]*children:)\r?\n((?:[ \t]+-\s*(?:!|[*&])[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return pattern.sub(_repl, content)

    def _inline_file_and_colorspace_transforms(self, content: str) -> str:
        # Match - !<FileTransform> or - !<ColorSpaceTransform>
        def _repl(m: re.Match[str]) -> str:
            tag_line = m.group(1).rstrip()
            props = [
                s
                for line in m.group(2).splitlines()
                if (s := line.strip()) and ":" in s and not s.startswith("-")
            ]
            return f"{tag_line} {{{', '.join(props)}}}\n"

        pattern = re.compile(
            r"^([ \t]*(?:-[ \t]*)?!<(?:FileTransform|ColorSpaceTransform)>)\r?\n((?:[ \t]+[a-zA-Z0-9_]+:\s*[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return pattern.sub(_repl, content)

    def apply(self, content: str) -> str:
        content = self._inline_builtins(content)
        content = self._inline_matrix_lists(content)
        content = self._inline_roles(content)
        content = self._inline_group_children(content)
        content = self._inline_file_and_colorspace_transforms(content)
        return content


def transform_flow_transforms(text: str) -> str:
    """Convenience function applying FlowTransformsTransform."""
    return FlowTransformsTransform().apply(text)
