"""Pipeline orchestrator for chaining OCIO minification transformations."""

from collections.abc import Iterator

from typing_extensions import Self

from ocio_minifier.transforms import (
    CompactAmfScalarsTransform,
    ElideDefaultsTransform,
    FloatPrecisionTransform,
    FlowCdlTransformsTransform,
    FlowTransformsTransform,
    StripDescriptionsTransform,
    Transform,
    YamlAnchorsTransform,
)


class MinificationPipeline:
    """Manages and executes a sequential series of minification transforms."""

    def __init__(
        self,
        transforms: list[Transform] | None = None,
        name: str = "Custom Pipeline",
    ):
        self.transforms: list[Transform] = list(transforms) if transforms else []
        self.name = name

    def add(self, transform: Transform) -> Self:
        """Add a transform to the pipeline and return self for chaining."""
        self.transforms.append(transform)
        return self

    def run(self, content: str) -> str:
        """Execute all transforms in sequence against the content."""
        result = content
        for t in self.transforms:
            result = t.apply(result)
        return result

    @property
    def is_lossy(self) -> bool:
        """Return True if any transform in the pipeline is marked as lossy."""
        return any(t.is_lossy for t in self.transforms)

    @property
    def transform_names(self) -> list[str]:
        """Return list of names of all configured transforms."""
        return [t.name for t in self.transforms]

    def __len__(self) -> int:
        return len(self.transforms)

    def __iter__(self) -> Iterator[Transform]:
        return iter(self.transforms)

    def __repr__(self) -> str:
        return f"<MinificationPipeline name={self.name!r} steps={len(self.transforms)} is_lossy={self.is_lossy}>"

    @classmethod
    def preset_syntactic(cls) -> "MinificationPipeline":
        """Lossless syntactic compression: elide defaults, compact AMF, flow inline, YAML anchors."""
        return cls(
            transforms=[
                ElideDefaultsTransform(),
                CompactAmfScalarsTransform(),
                FlowTransformsTransform(),
                FlowCdlTransformsTransform(),
                YamlAnchorsTransform(),
            ],
            name="Syntactic Lossless",
        )

    @classmethod
    def preset_aggressive(cls, precision: int | None = None) -> "MinificationPipeline":
        """Maximum compression: lossless syntactic transforms plus lossy description stripping and optional float rounding."""
        pipeline = cls.preset_syntactic()
        pipeline.name = "Aggressive (Lossy Descriptions)"
        pipeline.add(StripDescriptionsTransform())
        if precision is not None:
            pipeline.add(FloatPrecisionTransform(decimals=precision))
            pipeline.name += f" [Precision: {precision}]"
        return pipeline
