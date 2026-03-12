"""Translate scenes into recorder and compositor request shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.studio.exceptions import InvalidSceneConfigurationError
from core.studio.models import AudioConfig, CaptureSource, Crop, Scene, SourceKind, SourceTransform


@dataclass(frozen=True)
class RecordingRequest:
    """Current recorder-compatible request."""

    mode: str
    rect: Optional[tuple[int, int, int, int]]
    mic: Optional[str]
    system: bool
    plan: "SceneCompositionPlan"


@dataclass(frozen=True)
class VideoLayer:
    """Ordered visual layer for compositor support."""

    source_id: str
    name: str
    kind: SourceKind
    rect: Optional[tuple[int, int, int, int]]
    z_index: int
    opacity: float
    transform: SourceTransform
    supported: bool
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class AudioChannel:
    """Audio mix channel for mixer support."""

    source_id: str
    name: str
    target: Optional[str]
    volume: float
    muted: bool
    gain_db: float
    sync_offset_ms: int
    solo: bool
    monitoring_mode: str
    peak_level: float
    rms_level: float


@dataclass(frozen=True)
class SceneCompositionPlan:
    """Scene decomposition for output graph planning."""

    primary_video: VideoLayer
    overlays: tuple[VideoLayer, ...]
    audio_channels: tuple[AudioChannel, ...]
    system_audio_enabled: bool
    microphone_target: Optional[str]
    diagnostics: tuple[str, ...] = ()


class SceneRecordingPlanner:
    """Build recorder requests from scenes."""

    def build_request(self, scene: Scene) -> RecordingRequest:
        plan = self.build_plan(scene)
        if not plan.primary_video.supported:
            raise InvalidSceneConfigurationError("Primary video source is preview-only and cannot be recorded yet")
        return RecordingRequest(
            mode=self._resolve_mode(plan.primary_video.kind),
            rect=plan.primary_video.rect,
            mic=plan.microphone_target,
            system=plan.system_audio_enabled,
            plan=plan,
        )

    def build_plan(self, scene: Scene) -> SceneCompositionPlan:
        video_sources = scene.video_sources()
        if not video_sources:
            raise InvalidSceneConfigurationError("Scene must contain one enabled video source")

        layers = tuple(self._build_video_layer(source, primary=index == 0) for index, source in enumerate(video_sources))
        diagnostics = tuple(note for layer in layers for note in layer.diagnostics)
        return SceneCompositionPlan(
            primary_video=layers[0],
            overlays=layers[1:],
            audio_channels=tuple(self._build_audio_channel(source) for source in scene.audio_sources()),
            system_audio_enabled=self._has_system_audio(scene),
            microphone_target=self._resolve_microphone(scene),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _resolve_mode(kind: SourceKind) -> str:
        if kind == SourceKind.DISPLAY:
            return "screen"
        if kind == SourceKind.WINDOW:
            return "window"
        return "region"

    @staticmethod
    def _resolve_rect(source: CaptureSource) -> Optional[tuple[int, int, int, int]]:
        if source.kind == SourceKind.DISPLAY:
            return source.bounds.to_rect() if source.bounds else None
        if source.bounds is None:
            raise InvalidSceneConfigurationError("Window and region sources require bounds")
        return source.bounds.to_rect()

    def _build_video_layer(self, source: CaptureSource, primary: bool) -> VideoLayer:
        rect = self._resolve_rect(source)
        supported, diagnostics = self._resolve_support(source, primary)
        return VideoLayer(
            source_id=source.source_id,
            name=source.name,
            kind=source.kind,
            rect=self._transform_rect(rect, source.transform),
            z_index=source.z_index,
            opacity=source.opacity,
            transform=source.transform,
            supported=supported,
            diagnostics=diagnostics,
        )

    def _resolve_support(self, source: CaptureSource, primary: bool) -> tuple[bool, tuple[str, ...]]:
        notes = []
        transform = source.transform
        runtime_supported = source.kind in {SourceKind.DISPLAY, SourceKind.WINDOW, SourceKind.REGION}
        if not runtime_supported:
            notes.append(f"{source.kind.value} renders in preview only in the current runtime")
        if transform.rotation_deg and not primary:
            notes.append("overlay rotation is preview-only in the current ffmpeg runtime")
        if transform.rotation_deg and primary:
            notes.append("primary rotation is preview-only in the current ffmpeg runtime")
        return (runtime_supported, tuple(notes))

    def _transform_rect(
        self,
        rect: Optional[tuple[int, int, int, int]],
        transform: SourceTransform,
    ) -> Optional[tuple[int, int, int, int]]:
        if rect is None:
            return None
        x1, y1, x2, y2 = rect
        cropped = self._apply_crop((x1, y1, x2, y2), transform.crop)
        width = max(1, int((cropped[2] - cropped[0]) * transform.scale_x))
        height = max(1, int((cropped[3] - cropped[1]) * transform.scale_y))
        left = cropped[0] + transform.position_x
        top = cropped[1] + transform.position_y
        return (left, top, left + width, top + height)

    @staticmethod
    def _apply_crop(rect: tuple[int, int, int, int], crop: Crop) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = rect
        cropped_left = x1 + crop.left
        cropped_top = y1 + crop.top
        cropped_right = max(cropped_left + 1, x2 - crop.right)
        cropped_bottom = max(cropped_top + 1, y2 - crop.bottom)
        return (cropped_left, cropped_top, cropped_right, cropped_bottom)

    @staticmethod
    def _build_audio_channel(source: CaptureSource) -> AudioChannel:
        audio = source.audio
        return AudioChannel(
            source_id=source.source_id,
            name=source.name,
            target=source.target,
            volume=source.volume,
            muted=source.muted,
            gain_db=audio.gain_db,
            sync_offset_ms=audio.sync_offset_ms,
            solo=audio.solo,
            monitoring_mode=audio.monitoring_mode.value,
            peak_level=audio.peak_level,
            rms_level=audio.rms_level,
        )

    @staticmethod
    def _resolve_microphone(scene: Scene) -> Optional[str]:
        for source in scene.mixed_audio_sources():
            if source.kind == SourceKind.MICROPHONE:
                return source.target
        return None

    @staticmethod
    def _has_system_audio(scene: Scene) -> bool:
        return any(source.kind == SourceKind.SYSTEM_AUDIO for source in scene.mixed_audio_sources())
