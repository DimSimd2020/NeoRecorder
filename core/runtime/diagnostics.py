"""Diagnostics and recovery policy helpers."""

from __future__ import annotations

from collections import deque

from core.runtime.models import RecoveryAction, RuntimeEvent, RuntimeEventType


class DiagnosticsService:
    """Collect runtime events and suggest recovery actions."""

    def __init__(self, max_events: int = 50):
        self._events: deque[RuntimeEvent] = deque(maxlen=max_events)

    def report(self, event: RuntimeEvent) -> RecoveryAction:
        self._events.append(event)
        return self._decide_recovery(event)

    def recent_events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._events)

    def latest_summary(self) -> str:
        if not self._events:
            return "Runtime healthy"
        event = self._events[-1]
        return f"{event.event_type.value}: {event.message}"

    @staticmethod
    def _decide_recovery(event: RuntimeEvent) -> RecoveryAction:
        if event.event_type in {RuntimeEventType.ENCODER_FAILED, RuntimeEventType.OUTPUT_START_FAILED, RuntimeEventType.SESSION_RESTORE_FAILED}:
            return RecoveryAction.RETRY_WITH_SOFTWARE
        if event.event_type in {RuntimeEventType.MONITOR_LOST, RuntimeEventType.WINDOW_LOST, RuntimeEventType.DEVICE_LOST}:
            return RecoveryAction.REVALIDATE_SCENE
        if event.event_type == RuntimeEventType.FFMPEG_EXITED_UNEXPECTEDLY:
            return RecoveryAction.SAFE_STOP
        return RecoveryAction.NONE
