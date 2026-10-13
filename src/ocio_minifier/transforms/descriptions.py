"""Lossy description stripping transformation."""

import re


class StripDescriptionsTransform:
    """Strips documentation descriptions from config root, color spaces, and transforms."""

    name: str = "Strip Descriptions (Lossy)"
    description: str = "Removes documentation descriptions from config root, color spaces, and transforms"
    is_lossy: bool = True

    def apply(self, content: str) -> str:
        lines = content.splitlines(keepends=True)
        out: list[str] = []
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


def transform_strip_descriptions(text: str) -> str:
    """Convenience function applying StripDescriptionsTransform."""
    return StripDescriptionsTransform().apply(text)
