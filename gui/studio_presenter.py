"""Presentation helpers for the studio dashboard."""

from __future__ import annotations

from core.studio.models import Bounds, CaptureSource, Scene, SourceKind


SOURCE_KIND_LABELS = {
    SourceKind.DISPLAY: "Display",
    SourceKind.WINDOW: "Window",
    SourceKind.REGION: "Region",
    SourceKind.MICROPHONE: "Microphone",
    SourceKind.SYSTEM_AUDIO: "System Audio",
}


def format_source_kind(kind: SourceKind) -> str:
    """Return a human-readable source kind."""
    return SOURCE_KIND_LABELS.get(kind, kind.value)


def format_bounds(bounds: Bounds | None) -> str:
    """Return human-readable bounds."""
    if bounds is None:
        return "Fullscreen"
    return f"{bounds.x},{bounds.y} • {bounds.width}x{bounds.height}"


def format_source_caption(source: CaptureSource) -> str:
    """Return a compact source description."""
    if source.is_audio():
        suffix = "Muted" if source.muted else f"{int(source.volume * 100)}%"
        return f"{format_source_kind(source.kind)} • {suffix}"
    if source.kind == SourceKind.DISPLAY and source.display_index():
        return f"{format_source_kind(source.kind)} • D{source.display_index()} • Z{source.z_index}"
    return f"{format_source_kind(source.kind)} • Z{source.z_index}"


def format_scene_summary(scene: Scene) -> str:
    """Return scene summary for sidebar cards."""
    total = len(scene.sources)
    videos = len(scene.video_sources())
    audios = len(scene.audio_sources())
    return f"{total} sources • {videos} video • {audios} audio"


def format_preview_caption(scene: Scene) -> str:
    """Return preview summary text."""
    video_count = len(scene.video_sources())
    overlay_count = len(scene.overlay_video_sources())
    return f"{video_count} layers • {overlay_count} overlays"
