"""Studio mode session state for preview/program workflow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from core.studio.exceptions import SceneNotFoundError
from core.studio.models import StudioProject


class TransitionKind(str, Enum):
    """Supported studio transitions."""

    CUT = "cut"
    FADE = "fade"
    SLIDE = "slide"


@dataclass(frozen=True)
class TransitionSpec:
    """Transition settings."""

    kind: TransitionKind = TransitionKind.CUT
    duration_ms: int = 250


@dataclass(frozen=True)
class StudioSession:
    """Preview/program scene state."""

    preview_scene_id: str
    program_scene_id: str
    transition: TransitionSpec = TransitionSpec()

    def with_preview(self, scene_id: str) -> "StudioSession":
        return replace(self, preview_scene_id=scene_id)

    def with_transition(self, transition: TransitionSpec) -> "StudioSession":
        return replace(self, transition=transition)

    def with_program(self, scene_id: str) -> "StudioSession":
        return replace(self, program_scene_id=scene_id)


class StudioSessionService:
    """Manage studio-mode preview/program transitions."""

    def create_session(self, project: StudioProject) -> StudioSession:
        scene_id = project.active_scene_id
        return StudioSession(preview_scene_id=scene_id, program_scene_id=scene_id)

    def set_preview_scene(
        self,
        project: StudioProject,
        session: StudioSession,
        scene_id: str,
    ) -> StudioSession:
        self._require_scene(project, scene_id)
        return session.with_preview(scene_id)

    def set_transition(
        self,
        session: StudioSession,
        kind: TransitionKind,
        duration_ms: int = 250,
    ) -> StudioSession:
        duration = max(50, duration_ms)
        return session.with_transition(TransitionSpec(kind=kind, duration_ms=duration))

    def take(
        self,
        project: StudioProject,
        session: StudioSession,
    ) -> tuple[StudioProject, StudioSession]:
        self._require_scene(project, session.preview_scene_id)
        updated_project = project.with_scenes(list(project.scenes), active_scene_id=session.preview_scene_id)
        updated_session = session.with_program(session.preview_scene_id)
        return updated_project, updated_session

    @staticmethod
    def _require_scene(project: StudioProject, scene_id: str):
        if project.get_scene(scene_id) is None:
            raise SceneNotFoundError(f"Scene not found: {scene_id}")
