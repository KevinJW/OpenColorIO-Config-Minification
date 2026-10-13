"""Default field elision transformation."""

import re


class ElideDefaultsTransform:
    """Removes schema-redundant default fields and empty environments."""

    name: str = "Default Field Elision"
    description: str = (
        "Removes redundant default fields (equalitygroup: '', allocation: uniform, "
        "isdata: false, and compacts empty environments)"
    )
    is_lossy: bool = False

    def apply(self, content: str) -> str:
        # Strip equalitygroup: "" or ''
        content = re.sub(
            r'^[ \t]*equalitygroup:\s*["\'][\'"]\r?\n',
            "",
            content,
            flags=re.MULTILINE,
        )
        # Strip allocation: uniform
        content = re.sub(
            r"^[ \t]*allocation:\s*uniform\r?\n",
            "",
            content,
            flags=re.MULTILINE,
        )
        # Strip isdata: false
        content = re.sub(
            r"^[ \t]*isdata:\s*false\r?\n",
            "",
            content,
            flags=re.MULTILINE,
        )
        # Compact empty multiline environment: \n  {} to single line environment: {}
        content = re.sub(
            r"^[ \t]*environment:\r?\n[ \t]*\{\}\r?\n",
            "environment: {}\n",
            content,
            flags=re.MULTILINE,
        )
        return content


def transform_elide_defaults(text: str) -> str:
    """Convenience function applying ElideDefaultsTransform."""
    return ElideDefaultsTransform().apply(text)
