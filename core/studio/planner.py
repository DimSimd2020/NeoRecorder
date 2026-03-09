"""Translate scenes into the current recorder request shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.studio.exceptions import InvalidSceneConfigurationError
from core.studio.models import CaptureSource, Scene, SourceKind


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
    """Ordered visual layer for future compositor support."""

    source_id: str
    name: str
    kind: SourceKind
    rect: Optional[tuple[int, int, int, int]]
    z_index: int
    opacity: float


@dataclass(frozen=True)
class AudioChannel:
    """Audio mix channel for future mixer support."""

    source_id: str
    name: str
    target: Optional[str]
    volume: float
    muted: bool


@dataclass(frozen=True)
class SceneCompositionPlan:
    """Scene decomposition for output graph planning."""

    primary_video: VideoLayer
    overlays: tuple[VideoLayer, ...]
    audio_channels: tuple[AudioChannel, ...]
    system_audio_enabled: bool
    microphone_target: Optional[str]


class SceneRecordingPlanner:
    """Build recorder requests from scenes."""

    def build_request(self, scene: Scene) -> RecordingRequest:
        plan = self.build_plan(scene)
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

        layers = tuple(self._build_video_layer(source) for source in video_sources)
        audio_channels = tuple(self._build_audio_channel(source) for source in scene.audio_sources())
        return SceneCompositionPlan(
            primary_video=layers[0],
            overlays=layers[1:],
            audio_channels=audio_channels,
            system_audio_enabled=self._has_system_audio(scene),
            microphone_target=self._resolve_microphone(scene),
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

    def _build_video_layer(self, source: CaptureSource) -> VideoLayer:
        return VideoLayer(
            source_id=source.source_id,
            name=source.name,
            kind=source.kind,
            rect=self._resolve_rect(source),
            z_index=source.z_index,
            opacity=source.opacity,
        )

    @staticmethod
    def _build_audio_channel(source: CaptureSource) -> AudioChannel:
        return AudioChannel(
            source_id=source.source_id,
            name=source.name,
            target=source.target,
            volume=source.volume,
            muted=source.muted,
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
