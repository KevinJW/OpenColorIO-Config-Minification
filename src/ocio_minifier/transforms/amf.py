"""AMF transform IDs compaction transformation."""

import re


class CompactAmfScalarsTransform:
    """Compacts multiline block scalars for AMF transform IDs into single quoted strings."""

    name: str = "Compact AMF Scalars"
    description: str = "Compacts multiline AMF transform ID block scalars into single-line quoted strings with escaped newlines"
    is_lossy: bool = False

    def apply(self, content: str) -> str:
        def _repl(match: re.Match) -> str:
            indent = match.group(1)
            raw_lines = match.group(2).strip().splitlines()
            cleaned = "".join(
                f"{line.strip()}\\n" for line in raw_lines if line.strip()
            )
            return f'{indent}amf_transform_ids: "{cleaned}"\n'

        amf_pattern = re.compile(
            r"^([ \t]*)amf_transform_ids:\s*\|\r?\n((?:[ \t]+urn:[^\r\n]+\r?\n)+)",
            re.MULTILINE,
        )
        return amf_pattern.sub(_repl, content)


def transform_compact_amf_scalars(text: str) -> str:
    """Convenience function applying CompactAmfScalarsTransform."""
    return CompactAmfScalarsTransform().apply(text)
