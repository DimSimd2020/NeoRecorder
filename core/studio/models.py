"""Scene/source domain models for OBS-style backend evolution."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Optional


class SourceKind(str, Enum):
    """Supported source kinds for the current recorder backend."""

    DISPLAY = "display_capture"
    WINDOW = "window_capture"
    REGION = "region_capture"
    MICROPHONE = "microphone_input"
    SYSTEM_AUDIO = "system_audio"
    BROWSER = "browser_source"
    IMAGE = "image_source"
    TEXT = "text_source"
    COLOR = "color_source"
    MEDIA = "media_source"

    def is_audio(self) -> bool:
        return self in {self.MICROPHONE, self.SYSTEM_AUDIO}

    def is_video(self) -> bool:
        return not self.is_audio()


class MonitoringMode(str, Enum):
    OFF = "off"
    MONITOR_ONLY = "monitor_only"
    MONITOR_AND_OUTPUT = "monitor_and_output"


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
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, payload: dict[str, int]) -> "Bounds":
        return cls(
            x=payload["x"],
            y=payload["y"],
            width=payload["width"],
            height=payload["height"],
        )


@dataclass(frozen=True)
class Crop:
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def __post_init__(self):
        for name, value in self.to_dict().items():
            if value < 0:
                raise ValueError(f"{name} crop must be non-negative, got {value}")

    def to_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, int]) -> "Crop":
        return cls(
            left=payload.get("left", 0),
            top=payload.get("top", 0),
            right=payload.get("right", 0),
            bottom=payload.get("bottom", 0),
        )


@dataclass(frozen=True)
class SourceTransform:
    position_x: int = 0
    position_y: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0
    crop: Crop = field(default_factory=Crop)
    rotation_deg: float = 0.0
    visible: bool = True
    locked: bool = False

    def __post_init__(self):
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise ValueError("scale must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_x": self.position_x,
            "position_y": self.position_y,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "crop": self.crop.to_dict(),
            "rotation_deg": self.rotation_deg,
            "visible": self.visible,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, payload: Optional[dict[str, Any]]) -> "SourceTransform":
        if not payload:
            return cls()
        return cls(
            position_x=payload.get("position_x", 0),
            position_y=payload.get("position_y", 0),
            scale_x=payload.get("scale_x", 1.0),
            scale_y=payload.get("scale_y", 1.0),
            crop=Crop.from_dict(payload.get("crop", {})),
            rotation_deg=payload.get("rotation_deg", 0.0),
            visible=payload.get("visible", True),
            locked=payload.get("locked", False),
        )


@dataclass(frozen=True)
class AudioConfig:
    gain_db: float = 0.0
    sync_offset_ms: int = 0
    solo: bool = False
    monitoring_mode: MonitoringMode = MonitoringMode.OFF
    peak_level: float = 0.0
    rms_level: float = 0.0

    def __post_init__(self):
        for name, value in {"peak_level": self.peak_level, "rms_level": self.rms_level}.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "gain_db": self.gain_db,
            "sync_offset_ms": self.sync_offset_ms,
            "solo": self.solo,
            "monitoring_mode": self.monitoring_mode.value,
            "peak_level": self.peak_level,
            "rms_level": self.rms_level,
        }

    @classmethod
    def from_dict(cls, payload: Optional[dict[str, Any]]) -> "AudioConfig":
        if not payload:
            return cls()
        return cls(
            gain_db=payload.get("gain_db", 0.0),
            sync_offset_ms=payload.get("sync_offset_ms", 0),
            solo=payload.get("solo", False),
            monitoring_mode=MonitoringMode(payload.get("monitoring_mode", MonitoringMode.OFF.value)),
            peak_level=payload.get("peak_level", 0.0),
            rms_level=payload.get("rms_level", 0.0),
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
    transform: SourceTransform = field(default_factory=SourceTransform)
    audio: AudioConfig = field(default_factory=AudioConfig)

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

    def is_visible(self) -> bool:
        return self.enabled and self.transform.visible

    def is_locked(self) -> bool:
        return self.transform.locked

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

    def copy_with(self, **changes) -> "CaptureSource":
        metadata = changes.pop("metadata", None)
        transform = changes.pop("transform", None)
        audio = changes.pop("audio", None)
        return replace(
            self,
            metadata=dict(self.metadata if metadata is None else metadata),
            transform=self.transform if transform is None else transform,
            audio=self.audio if audio is None else audio,
            **changes,
        )

    def with_enabled(self, enabled: bool) -> "CaptureSource":
        return self.copy_with(enabled=enabled)

    def with_z_index(self, z_index: int) -> "CaptureSource":
        return self.copy_with(z_index=z_index)

    def with_volume(self, volume: float) -> "CaptureSource":
        return self.copy_with(volume=volume)

    def with_muted(self, muted: bool) -> "CaptureSource":
        return self.copy_with(muted=muted)

    def with_opacity(self, opacity: float) -> "CaptureSource":
        return self.copy_with(opacity=opacity)

    def with_transform(self, **changes) -> "CaptureSource":
        return self.copy_with(transform=replace(self.transform, **changes))

    def with_audio(self, **changes) -> "CaptureSource":
        return self.copy_with(audio=replace(self.audio, **changes))

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
            "transform": self.transform.to_dict(),
            "audio": self.audio.to_dict(),
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
            transform=SourceTransform.from_dict(payload.get("transform")),
            audio=AudioConfig.from_dict(payload.get("audio")),
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
        return tuple(source for source in self.ordered_sources() if source.is_video() and source.is_visible())

    def mixed_audio_sources(self) -> tuple[CaptureSource, ...]:
        candidates = tuple(source for source in self.audio_sources() if source.is_mixed_audio())
        if not any(source.audio.solo for source in candidates):
            return candidates
        return tuple(source for source in candidates if source.audio.solo)

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
        return self.with_sources([source for source in self.sources if source.source_id != source_id])

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
        return StudioProject(
            project_id=self.project_id,
            name=self.name,
            scenes=tuple(scenes),
            active_scene_id=active_scene_id or self.active_scene_id,
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
