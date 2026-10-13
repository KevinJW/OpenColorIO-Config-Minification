"""YAML anchor and alias transformation for repeated matrix deduplication."""

import re


class YamlAnchorsTransform:
    """Deduplicates repeated identical MatrixTransforms using standard YAML &anchors and *aliases."""

    name: str = "YAML Anchors & Aliases"
    description: str = "Deduplicates repeated identical MatrixTransforms using standard YAML &anchors and *aliases"
    is_lossy: bool = False

    def apply(self, content: str) -> str:
        mat_pattern: re.Pattern[str] = re.compile(
            r"(!<MatrixTransform>\s*\{matrix:\s*\[([0-9., \-eE]+)\]\})"
        )
        occurrences = mat_pattern.findall(content)

        val_counts: dict[str, int] = {}
        for _full_node, mat_str in occurrences:
            norm_key = ",".join(x.strip() for x in mat_str.split(","))
            val_counts[norm_key] = val_counts.get(norm_key, 0) + 1

        anchors = {
            key: f"matrix_ref_{i}"
            for i, (key, count) in enumerate(val_counts.items())
            if count > 1
        }
        seen: set[str] = set()

        def _replace_anchor(match: re.Match[str]) -> str:
            full_node = match.group(1)
            mat_str = match.group(2)
            norm_key = ",".join(x.strip() for x in mat_str.split(","))
            if norm_key in anchors:
                anchor_name = anchors[norm_key]
                if norm_key not in seen:
                    seen.add(norm_key)
                    return f"&{anchor_name} {full_node}"
                return f"*{anchor_name}"
            return full_node

        result: str = mat_pattern.sub(_replace_anchor, content)
        return result


def transform_yaml_anchors(text: str) -> str:
    """Convenience function applying YamlAnchorsTransform."""
    return YamlAnchorsTransform().apply(text)
