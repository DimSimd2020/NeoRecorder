"""Broadcast orchestration for recording and streaming."""

from __future__ import annotations

from typing import Optional

from core.runtime.diagnostics import DiagnosticsService
from core.runtime.persistence import RuntimeArtifactStore
from core.runtime.models import (
    BroadcastRuntimeState,
    BroadcastStatus,
    OutputMode,
    OutputSession,
    OutputSessionSnapshot,
    RecoveryAction,
    RuntimeEvent,
    RuntimeEventType,
    StreamSettings,
    StreamState,
)


class BroadcastOrchestrator:
    """Coordinate runtime state, diagnostics, and recorder operations."""

    def __init__(self, recorder, diagnostics: Optional[DiagnosticsService] = None):
        self.recorder = recorder
        self.diagnostics = diagnostics or DiagnosticsService()
        self.artifacts = RuntimeArtifactStore()
        self.runtime_state = BroadcastRuntimeState.IDLE
        self.stream_settings = StreamSettings()
        self.output_session = OutputSession()
        self.output_snapshot = OutputSessionSnapshot()
        self._recovery_attempts = 0

    def mark_preview_ready(self):
        if self.runtime_state == BroadcastRuntimeState.IDLE:
            self.runtime_state = BroadcastRuntimeState.PREVIEW_READY

    def start_recording(self, request) -> Optional[str]:
        output = self._start(request=request, stream_settings=None)
        return output

    def start_streaming(self, request, stream_settings: StreamSettings) -> Optional[str]:
        output = self._start(request=request, stream_settings=stream_settings, record_to_file=False)
        return output

    def start_recording_and_streaming(self, request, stream_settings: StreamSettings) -> Optional[str]:
        output = self._start(request=request, stream_settings=None)
        if output is None:
            self._refresh_output_context()
            return None
        self.stream_settings = stream_settings
        if not self.recorder.enable_stream(stream_settings):
            self._handle_event(RuntimeEvent(RuntimeEventType.OUTPUT_START_FAILED, "Failed to start stream output"))
            self.runtime_state = BroadcastRuntimeState.RECORDING
            self._refresh_output_context()
            return output
        self.runtime_state = BroadcastRuntimeState.RECORDING_AND_STREAMING
        self._refresh_output_context()
        return output

    def _start(self, request, stream_settings=None, record_to_file: bool = True) -> Optional[str]:
        self.runtime_state = BroadcastRuntimeState.PREPARING
        output = self.recorder.start_request(request, stream_settings=stream_settings, record_to_file=record_to_file)
        if output is None and not (stream_settings and stream_settings.is_configured() and not record_to_file):
            self._handle_event(RuntimeEvent(RuntimeEventType.OUTPUT_START_FAILED, "Failed to start output"))
            self._refresh_output_context()
            return None
        self.stream_settings = stream_settings or StreamSettings()
        self.runtime_state = self._resolve_running_state(record_to_file, self.stream_settings.is_configured())
        self._recovery_attempts = 0
        self._refresh_output_context()
        return output

    def stop(self):
        result = self.recorder.stop()
        self.runtime_state = BroadcastRuntimeState.PREVIEW_READY
        self._refresh_output_context()
        self.artifacts.clear()
        return result

    def pause(self) -> bool:
        return self.recorder.pause()

    def resume(self) -> bool:
        return self.recorder.resume()

    def shutdown(self):
        if self.runtime_state not in {BroadcastRuntimeState.IDLE, BroadcastRuntimeState.PREVIEW_READY}:
            return self.stop()
        return None

    def enable_stream(self, stream_settings: StreamSettings) -> bool:
        self.stream_settings = stream_settings
        if not self.recorder.enable_stream(stream_settings):
            self._handle_event(RuntimeEvent(RuntimeEventType.OUTPUT_START_FAILED, "Failed to hot-start stream output"))
            self._refresh_output_context()
            return False
        self._refresh_output_context()
        self.runtime_state = self._resolve_running_state(self.output_session.mode != OutputMode.STREAM, True)
        return True

    def disable_stream(self) -> bool:
        stopped = self.recorder.disable_stream()
        self._refresh_output_context()
        if not stopped:
            return False
        self.runtime_state = BroadcastRuntimeState.RECORDING if self.recorder.is_recording else BroadcastRuntimeState.PREVIEW_READY
        return True

    def report_event(self, event: RuntimeEvent) -> RecoveryAction:
        return self._handle_event(event)

    def status(self) -> BroadcastStatus:
        self._refresh_output_context()
        return BroadcastStatus(
            runtime_state=self.runtime_state,
            recorder_state=self.recorder.state,
            stream_enabled=self.output_session.stream_state in {StreamState.LIVE, StreamState.RECONNECTING, StreamState.STARTING},
            diagnostics_summary=self.diagnostics.latest_summary(),
        )

    def _handle_event(self, event: RuntimeEvent) -> RecoveryAction:
        action = self.diagnostics.report(event)
        self._persist_artifact()
        if action == RecoveryAction.NONE:
            return action
        if action == RecoveryAction.RETRY_WITH_SOFTWARE:
            if self._recover_output_session(prefer_software=True):
                return action
            self.runtime_state = BroadcastRuntimeState.FAILED
            self._refresh_output_context()
            return action
        if action == RecoveryAction.SAFE_STOP:
            self.stop()
            self.runtime_state = BroadcastRuntimeState.FAILED
            self._refresh_output_context()
            return action
        self.runtime_state = BroadcastRuntimeState.RECOVERING
        return action

    def restore_output_session(self, prefer_software: bool = False) -> Optional[str]:
        if not self.output_snapshot.is_recoverable():
            return None
        result = self.recorder.restore_output_session(self.output_snapshot, prefer_software=prefer_software)
        self._refresh_output_context()
        if result is None:
            self.diagnostics.report(RuntimeEvent(RuntimeEventType.SESSION_RESTORE_FAILED, "Failed to restore output session"))
            self._persist_artifact()
            self.runtime_state = BroadcastRuntimeState.FAILED
            return None
        self.runtime_state = self._resolve_running_state(
            self.output_snapshot.record_to_file,
            self.output_session.stream_state in {StreamState.LIVE, StreamState.RECONNECTING, StreamState.STARTING},
        )
        self._persist_artifact()
        return result

    def _recover_output_session(self, prefer_software: bool) -> bool:
        if not self.output_snapshot.is_recoverable() or self._recovery_attempts >= 1:
            return False
        self._recovery_attempts += 1
        self.runtime_state = BroadcastRuntimeState.RECOVERING
        return self.restore_output_session(prefer_software=prefer_software) is not None

    def _refresh_output_context(self):
        self.output_session = self.recorder.get_output_session()
        self.output_snapshot = self.recorder.snapshot_output_session()
        self._persist_artifact()

    def _persist_artifact(self):
        if self.output_snapshot.is_recoverable() or self.output_session.is_active() or self.diagnostics.recent_events():
            self.artifacts.save(self.output_snapshot, self.output_session, self.diagnostics.recent_events())

    @staticmethod
    def _resolve_running_state(record_to_file: bool, stream_enabled: bool) -> BroadcastRuntimeState:
        if record_to_file and stream_enabled:
            return BroadcastRuntimeState.RECORDING_AND_STREAMING
        if stream_enabled:
            return BroadcastRuntimeState.STREAMING
        return BroadcastRuntimeState.RECORDING
