"""Persistence for runtime recovery artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from config import OUTPUT_SESSION_REPORT_FILE
from core.runtime.models import OutputSession, OutputSessionSnapshot, RuntimeEvent, StreamSettings


class RuntimeArtifactStore:
    """Persist output-session artifacts for recovery diagnostics."""

    def __init__(self, path: str | Path = OUTPUT_SESSION_REPORT_FILE):
        self.path = Path(path)

    def save(
        self,
        snapshot: OutputSessionSnapshot,
        session: OutputSession,
        diagnostics: tuple[RuntimeEvent, ...],
    ):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "snapshot": self._serialize(snapshot),
            "session": self._serialize(session),
            "diagnostics": [self._serialize(event) for event in diagnostics],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def clear(self):
        if self.path.exists():
            self.path.unlink()

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _serialize(self, value: Any):
        if is_dataclass(value):
            return self._serialize(asdict(value))
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize(item) for item in value]
        if hasattr(value, "value"):
            return value.value
        if hasattr(value, "__dict__") and not isinstance(value, (str, bytes, int, float, bool)):
            return {
                "type": value.__class__.__name__,
                "data": {key: self._serialize(item) for key, item in vars(value).items()},
            }
        return value
