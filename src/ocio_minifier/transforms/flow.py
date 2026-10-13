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
            body = m.group(2)
            pairs: list[str] = []
            for line in body.splitlines():
                s = line.strip()
                if s and ":" in s and not s.startswith("#"):
                    pairs.append(s)
            if pairs:
                return f"{prefix} {{{', '.join(pairs)}}}\n"
            return m.group(0)

        pattern = re.compile(
            r"^(roles:)\r?\n((?:[ \t]+[a-zA-Z0-9_\-]+:\s*[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return pattern.sub(_repl, content)

    def _inline_group_children(self, content: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            prefix = m.group(1)
            body = m.group(2)
            items: list[str] = []
            for line in body.splitlines():
                s = line.strip()
                if s.startswith("- "):
                    items.append(s[2:].strip())
            if items:
                return f"{prefix} [{', '.join(items)}]\n"
            return m.group(0)

        pattern = re.compile(
            r"^([ \t]*children:)\r?\n((?:[ \t]+-\s*(?:!|[*&])[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return pattern.sub(_repl, content)

    def _inline_file_and_colorspace_transforms(self, content: str) -> str:
        # Match - !<FileTransform> or - !<ColorSpaceTransform>
        def _repl(m: re.Match[str]) -> str:
            tag_line = m.group(1).rstrip()
            body = m.group(2)
            props: list[str] = []
            for line in body.splitlines():
                s = line.strip()
                if s and ":" in s and not s.startswith("-"):
                    props.append(s)
            if props:
                return f"{tag_line} {{{', '.join(props)}}}\n"
            return m.group(0)

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
