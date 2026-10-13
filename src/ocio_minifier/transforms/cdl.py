"""CDL transform inlining transformation."""

import re


class FlowCdlTransformsTransform:
    """Inlines CDLTransform array properties (slope, offset, power, sat) into flow mappings."""

    name: str = "CDL Transform Flow Inlining"
    description: str = (
        "Inlines CDLTransform array properties into compact flow mapping syntax"
    )
    is_lossy: bool = False

    def apply(self, content: str) -> str:
        # Match array properties: slope, offset, power
        def _clean_array(match: re.Match[str]) -> str:
            prefix = match.group(1).rstrip()
            raw_nums = match.group(2)
            cleaned = ", ".join(x.strip() for x in raw_nums.split(",") if x.strip())
            return f"{prefix} [{cleaned}]"

        array_pattern = re.compile(
            r"^([ \t]*(?:slope|offset|power|sat):\s*)\[([0-9., \r\n\-eE]+)\]",
            re.MULTILINE,
        )
        return array_pattern.sub(_clean_array, content)


def transform_flow_cdl_transforms(text: str) -> str:
    """Convenience function applying FlowCdlTransformsTransform."""
    return FlowCdlTransformsTransform().apply(text)
