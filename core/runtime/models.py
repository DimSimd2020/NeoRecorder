"""Runtime state and output models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RecorderState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    FAILED = "failed"


class BroadcastRuntimeState(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    PREVIEW_READY = "preview_ready"
    STREAMING = "streaming"
    RECORDING = "recording"
    RECORDING_AND_STREAMING = "recording_and_streaming"
    RECOVERING = "recovering"
    FAILED = "failed"


class RuntimeEventType(str, Enum):
    ENCODER_FAILED = "encoder_failed"
    OUTPUT_START_FAILED = "output_start_failed"
    STREAM_CONNECT_FAILED = "stream_connect_failed"
    STREAM_BRIDGE_FAILED = "stream_bridge_failed"
    SESSION_RESTORE_FAILED = "session_restore_failed"
    MONITOR_LOST = "monitor_lost"
    WINDOW_LOST = "window_lost"
    DEVICE_LOST = "device_lost"
    FFMPEG_EXITED_UNEXPECTEDLY = "ffmpeg_exited_unexpectedly"
    UNSUPPORTED_TRANSFORM = "unsupported_transform"
    INFO = "info"


class RecoveryAction(str, Enum):
    NONE = "none"
    RETRY_WITH_SOFTWARE = "retry_with_software"
    REVALIDATE_SCENE = "revalidate_scene"
    SAFE_STOP = "safe_stop"


class StreamServicePreset(str, Enum):
    CUSTOM_RTMP = "custom_rtmp"
    TWITCH = "twitch"
    YOUTUBE = "youtube"


class OutputMode(str, Enum):
    IDLE = "idle"
    RECORD = "record"
    STREAM = "stream"
    RECORD_AND_STREAM = "record_and_stream"


class StreamState(str, Enum):
    DISABLED = "disabled"
    STARTING = "starting"
    LIVE = "live"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: RuntimeEventType
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    source_id: Optional[str] = None


@dataclass(frozen=True)
class StreamSettings:
    enabled: bool = False
    service_preset: StreamServicePreset = StreamServicePreset.CUSTOM_RTMP
    server_url: str = ""
    stream_key: str = ""
    encoder_profile: str = "main"
    target_bitrate: int = 6000

    def is_configured(self) -> bool:
        return self.enabled and bool(self.server_url.strip()) and bool(self.stream_key.strip())

    def output_url(self) -> str:
        base = self.server_url.rstrip("/")
        key = self.stream_key.lstrip("/")
        return f"{base}/{key}" if key else base


@dataclass(frozen=True)
class BroadcastStatus:
    runtime_state: BroadcastRuntimeState = BroadcastRuntimeState.IDLE
    recorder_state: RecorderState = RecorderState.IDLE
    stream_enabled: bool = False
    diagnostics_summary: str = ""


@dataclass(frozen=True)
class OutputSession:
    mode: OutputMode = OutputMode.IDLE
    record_path: Optional[str] = None
    bridge_url: Optional[str] = None
    stream_state: StreamState = StreamState.DISABLED
    stream_url: Optional[str] = None
    reconnect_attempts: int = 0
    reconnect_backoff_seconds: float = 0.0
    last_error: str = ""
    software_fallback_active: bool = False

    def is_active(self) -> bool:
        return self.mode != OutputMode.IDLE


@dataclass(frozen=True)
class OutputSessionSnapshot:
    request: Any = None
    mode: OutputMode = OutputMode.IDLE
    stream_settings: Optional[StreamSettings] = None
    record_to_file: bool = True
    software_fallback_active: bool = False

    def is_recoverable(self) -> bool:
        return self.request is not None and self.mode != OutputMode.IDLE
