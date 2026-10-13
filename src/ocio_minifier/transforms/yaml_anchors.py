"""YAML anchor and alias transformation for repeated transform and view deduplication."""

import re

SUPPORTED_TAGS: dict[str, str] = {
    "MatrixTransform": "matrix_ref",
    "BuiltinTransform": "builtin_ref",
    "LogCameraTransform": "logcam_ref",
    "ExponentTransform": "exponent_ref",
    "ExponentWithLinearTransform": "explin_ref",
    "CDLTransform": "cdl_ref",
    "RangeTransform": "range_ref",
    "View": "view_ref",
}


class YamlAnchorsTransform:
    """Deduplicates repeated identical transforms and view mappings using standard YAML &anchors and *aliases."""

    name: str = "YAML Anchors & Aliases"
    description: str = (
        "Deduplicates repeated identical transforms (Matrix, Builtin, LogCamera, Exponent, CDL, Range) "
        "and Views using standard YAML &anchors and *aliases"
    )
    is_lossy: bool = False

    def __init__(self, supported_tags: dict[str, str] | None = None):
        self.supported_tags = supported_tags or dict(SUPPORTED_TAGS)

    def apply(self, content: str) -> str:
        pattern: re.Pattern[str] = re.compile(
            r"(?<![&*a-zA-Z0-9_\-])(!<([A-Za-z0-9]+)>\s*\{[^\r\n{}]+\})"
        )
        occurrences = pattern.findall(content)

        # Count normalized representations for each supported tag
        norm_counts: dict[tuple[str, str], int] = {}
        for full_node, tag_name in occurrences:
            if tag_name not in self.supported_tags:
                continue
            norm_key = (tag_name, re.sub(r"\s+", " ", full_node).strip())
            norm_counts[norm_key] = norm_counts.get(norm_key, 0) + 1

        # Generate unique anchor identifiers per tag namespace
        tag_indices: dict[str, int] = {}
        anchors: dict[tuple[str, str], str] = {}
        for (tag_name, norm_node), count in norm_counts.items():
            if count > 1:
                idx = tag_indices.get(tag_name, 0)
                tag_indices[tag_name] = idx + 1
                prefix = self.supported_tags[tag_name]
                anchors[(tag_name, norm_node)] = f"{prefix}_{idx}"

        seen: set[tuple[str, str]] = set()

        def _replace_anchor(match: re.Match[str]) -> str:
            full_node = match.group(1)
            tag_name = match.group(2)
            norm_key = (tag_name, re.sub(r"\s+", " ", full_node).strip())
            if norm_key in anchors:
                anchor_name = anchors[norm_key]
                if norm_key not in seen:
                    seen.add(norm_key)
                    return f"&{anchor_name} {full_node}"
                return f"*{anchor_name}"
            return full_node

        result: str = pattern.sub(_replace_anchor, content)
        return result


def transform_yaml_anchors(text: str) -> str:
    """Convenience function applying YamlAnchorsTransform."""
    return YamlAnchorsTransform().apply(text)
