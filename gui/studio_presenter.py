"""Presentation helpers for the studio dashboard."""

from __future__ import annotations

from core.studio.models import Bounds, CaptureSource, Scene, SourceKind


SOURCE_KIND_LABELS = {
    SourceKind.DISPLAY: "Display",
    SourceKind.WINDOW: "Window",
    SourceKind.REGION: "Region",
    SourceKind.MICROPHONE: "Microphone",
    SourceKind.SYSTEM_AUDIO: "System Audio",
    SourceKind.BROWSER: "Browser",
    SourceKind.IMAGE: "Image",
    SourceKind.TEXT: "Text",
    SourceKind.COLOR: "Color",
    SourceKind.MEDIA: "Media",
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
        status = "Muted" if source.muted else f"{int(source.volume * 100)}%"
        flags = _join_flags(
            status,
            f"{source.audio.gain_db:+.1f}dB" if source.audio.gain_db else None,
            "Solo" if source.audio.solo else None,
            source.audio.monitoring_mode.value.replace("_", " ").title()
            if source.audio.monitoring_mode.value != "off"
            else None,
        )
        return f"{format_source_kind(source.kind)} • {flags}"
    if source.kind == SourceKind.DISPLAY and source.display_index():
        prefix = f"{format_source_kind(source.kind)} • D{source.display_index()} • Z{source.z_index}"
        return _append_video_flags(prefix, source)
    return _append_video_flags(f"{format_source_kind(source.kind)} • Z{source.z_index}", source)


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


def _append_video_flags(prefix: str, source: CaptureSource) -> str:
    flags = _join_flags(
        "Hidden" if not source.transform.visible else None,
        "Locked" if source.transform.locked else None,
        f"Rot {int(source.transform.rotation_deg)}°" if source.transform.rotation_deg else None,
    )
    return f"{prefix} • {flags}" if flags else prefix


def _join_flags(*parts: str | None) -> str:
    return " • ".join(part for part in parts if part)
