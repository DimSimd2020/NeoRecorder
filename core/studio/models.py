"""Scene/source domain models for OBS-style backend evolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceKind(str, Enum):
    """Supported source kinds for the current recorder backend."""

    DISPLAY = "display_capture"
    WINDOW = "window_capture"
    REGION = "region_capture"
    MICROPHONE = "microphone_input"
    SYSTEM_AUDIO = "system_audio"

    def is_audio(self) -> bool:
        return self in {self.MICROPHONE, self.SYSTEM_AUDIO}

    def is_video(self) -> bool:
        return not self.is_audio()


@dataclass(frozen=True)
class Bounds:
    """Normalized capture bounds."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        self._validate_dimension("width", self.width)
        self._validate_dimension("height", self.height)

    @staticmethod
    def _validate_dimension(name: str, value: int):
        if value < 1:
            raise ValueError(f"{name} must be positive, got {value}")

    @classmethod
    def from_rect(cls, rect: tuple[int, int, int, int]) -> "Bounds":
        x1, y1, x2, y2 = rect
        x = min(x1, x2)
        y = min(y1, y2)
        return cls(x=x, y=y, width=abs(x2 - x1), height=abs(y2 - y1))

    def to_rect(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, int]) -> "Bounds":
        return cls(
            x=payload["x"],
            y=payload["y"],
            width=payload["width"],
            height=payload["height"],
        )


@dataclass(frozen=True)
class CaptureSource:
    """A single scene source."""

    source_id: str
    name: str
    kind: SourceKind
    enabled: bool = True
    bounds: Optional[Bounds] = None
    target: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    z_index: int = 0
    volume: float = 1.0
    muted: bool = False
    opacity: float = 1.0

    def __post_init__(self):
        self._validate_range("volume", self.volume)
        self._validate_range("opacity", self.opacity)

    @staticmethod
    def _validate_range(name: str, value: float):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    def is_audio(self) -> bool:
        return self.kind.is_audio()

    def is_video(self) -> bool:
        return self.kind.is_video()

    def display_index(self) -> Optional[int]:
        if self.kind != SourceKind.DISPLAY:
            return None
        return self.metadata.get("monitor_index", 1)

    def display_name(self) -> Optional[str]:
        if self.kind != SourceKind.DISPLAY:
            return None
        return self.metadata.get("monitor_name")

    def is_mixed_audio(self) -> bool:
        return self.is_audio() and self.enabled and not self.muted and self.volume > 0.0

    def with_enabled(self, enabled: bool) -> "CaptureSource":
        return CaptureSource(
            source_id=self.source_id,
            name=self.name,
            kind=self.kind,
            enabled=enabled,
            bounds=self.bounds,
            target=self.target,
            metadata=dict(self.metadata),
            z_index=self.z_index,
            volume=self.volume,
            muted=self.muted,
            opacity=self.opacity,
        )

    def with_z_index(self, z_index: int) -> "CaptureSource":
        return CaptureSource(
            source_id=self.source_id,
            name=self.name,
            kind=self.kind,
            enabled=self.enabled,
            bounds=self.bounds,
            target=self.target,
            metadata=dict(self.metadata),
            z_index=z_index,
            volume=self.volume,
            muted=self.muted,
            opacity=self.opacity,
        )

    def with_volume(self, volume: float) -> "CaptureSource":
        return CaptureSource(
            source_id=self.source_id,
            name=self.name,
            kind=self.kind,
            enabled=self.enabled,
            bounds=self.bounds,
            target=self.target,
            metadata=dict(self.metadata),
            z_index=self.z_index,
            volume=volume,
            muted=self.muted,
            opacity=self.opacity,
        )

    def with_muted(self, muted: bool) -> "CaptureSource":
        return CaptureSource(
            source_id=self.source_id,
            name=self.name,
            kind=self.kind,
            enabled=self.enabled,
            bounds=self.bounds,
            target=self.target,
            metadata=dict(self.metadata),
            z_index=self.z_index,
            volume=self.volume,
            muted=muted,
            opacity=self.opacity,
        )

    def with_opacity(self, opacity: float) -> "CaptureSource":
        return CaptureSource(
            source_id=self.source_id,
            name=self.name,
            kind=self.kind,
            enabled=self.enabled,
            bounds=self.bounds,
            target=self.target,
            metadata=dict(self.metadata),
            z_index=self.z_index,
            volume=self.volume,
            muted=self.muted,
            opacity=opacity,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "kind": self.kind.value,
            "enabled": self.enabled,
            "bounds": self.bounds.to_dict() if self.bounds else None,
            "target": self.target,
            "metadata": dict(self.metadata),
            "z_index": self.z_index,
            "volume": self.volume,
            "muted": self.muted,
            "opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CaptureSource":
        bounds = payload.get("bounds")
        return cls(
            source_id=payload["source_id"],
            name=payload["name"],
            kind=SourceKind(payload["kind"]),
            enabled=payload.get("enabled", True),
            bounds=Bounds.from_dict(bounds) if bounds else None,
            target=payload.get("target"),
            metadata=dict(payload.get("metadata", {})),
            z_index=payload.get("z_index", 0),
            volume=payload.get("volume", 1.0),
            muted=payload.get("muted", False),
            opacity=payload.get("opacity", 1.0),
        )


@dataclass(frozen=True)
class Scene:
    """A collection of sources."""

    scene_id: str
    name: str
    sources: tuple[CaptureSource, ...] = ()

    def get_source(self, source_id: str) -> Optional[CaptureSource]:
        return next((source for source in self.sources if source.source_id == source_id), None)

    def enabled_sources(self) -> tuple[CaptureSource, ...]:
        return tuple(source for source in self.sources if source.enabled)

    def ordered_sources(self) -> tuple[CaptureSource, ...]:
        return tuple(sorted(self.enabled_sources(), key=lambda source: source.z_index))

    def audio_sources(self) -> tuple[CaptureSource, ...]:
        return tuple(source for source in self.ordered_sources() if source.is_audio())

    def video_sources(self) -> tuple[CaptureSource, ...]:
        return tuple(source for source in self.ordered_sources() if source.is_video())

    def mixed_audio_sources(self) -> tuple[CaptureSource, ...]:
        return tuple(source for source in self.audio_sources() if source.is_mixed_audio())

    def primary_video_source(self) -> Optional[CaptureSource]:
        video_sources = self.video_sources()
        if not video_sources:
            return None
        return video_sources[0]

    def overlay_video_sources(self) -> tuple[CaptureSource, ...]:
        video_sources = self.video_sources()
        return video_sources[1:]

    def with_sources(self, sources: list[CaptureSource]) -> "Scene":
        return Scene(scene_id=self.scene_id, name=self.name, sources=tuple(sources))

    def add_source(self, source: CaptureSource) -> "Scene":
        return self.with_sources([*self.sources, source])

    def replace_source(self, source: CaptureSource) -> "Scene":
        updated = [item if item.source_id != source.source_id else source for item in self.sources]
        return self.with_sources(updated)

    def remove_source(self, source_id: str) -> "Scene":
        sources = [source for source in self.sources if source.source_id != source_id]
        return self.with_sources(sources)

    def rename(self, name: str) -> "Scene":
        return Scene(scene_id=self.scene_id, name=name, sources=self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "sources": [source.to_dict() for source in self.sources],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Scene":
        return cls(
            scene_id=payload["scene_id"],
            name=payload["name"],
            sources=tuple(CaptureSource.from_dict(item) for item in payload.get("sources", [])),
        )


@dataclass(frozen=True)
class StudioProject:
    """Persisted studio project."""

    project_id: str
    name: str
    scenes: tuple[Scene, ...]
    active_scene_id: str
    version: int = 1

    def active_scene(self) -> Scene:
        return next(scene for scene in self.scenes if scene.scene_id == self.active_scene_id)

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return next((scene for scene in self.scenes if scene.scene_id == scene_id), None)

    def with_scenes(self, scenes: list[Scene], active_scene_id: Optional[str] = None) -> "StudioProject":
        resolved_active = active_scene_id or self.active_scene_id
        return StudioProject(
            project_id=self.project_id,
            name=self.name,
            scenes=tuple(scenes),
            active_scene_id=resolved_active,
            version=self.version,
        )

    def rename(self, name: str) -> "StudioProject":
        return StudioProject(
            project_id=self.project_id,
            name=name,
            scenes=self.scenes,
            active_scene_id=self.active_scene_id,
            version=self.version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "version": self.version,
            "active_scene_id": self.active_scene_id,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StudioProject":
        return cls(
            project_id=payload["project_id"],
            name=payload["name"],
            version=payload.get("version", 1),
            active_scene_id=payload["active_scene_id"],
            scenes=tuple(Scene.from_dict(item) for item in payload.get("scenes", [])),
        )
