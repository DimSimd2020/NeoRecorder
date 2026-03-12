"""Project and scene management for the studio backend."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from core.studio.exceptions import SceneNotFoundError, SourceNotFoundError
from core.studio.models import Bounds, CaptureSource, MonitoringMode, Scene, SourceKind, StudioProject


class StudioProjectService:
    """Manage scenes, sources and project persistence."""

    def __init__(self, id_factory=None):
        self._id_factory = id_factory or self._create_id

    def create_project(self, name: str, scene_name: str = "Main Scene") -> StudioProject:
        scene = self.create_scene(scene_name)
        return StudioProject(
            project_id=self._id_factory(),
            name=name,
            scenes=(scene,),
            active_scene_id=scene.scene_id,
        )

    def create_scene(self, name: str) -> Scene:
        return Scene(scene_id=self._id_factory(), name=name)

    def save_project(self, project: StudioProject, path: str | Path):
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def load_project(self, path: str | Path) -> StudioProject:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return StudioProject.from_dict(payload)

    def add_scene(self, project: StudioProject, scene_name: str) -> StudioProject:
        return project.with_scenes([*project.scenes, self.create_scene(scene_name)])

    def duplicate_scene(
        self,
        project: StudioProject,
        scene_id: str,
        name: Optional[str] = None,
    ) -> StudioProject:
        scene = self._require_scene(project, scene_id)
        duplicated = Scene(
            scene_id=self._id_factory(),
            name=name or f"{scene.name} Copy",
            sources=tuple(self._clone_source(source) for source in scene.sources),
        )
        return project.with_scenes([*project.scenes, duplicated], active_scene_id=duplicated.scene_id)

    def rename_scene(self, project: StudioProject, scene_id: str, name: str) -> StudioProject:
        return self._replace_scene(project, self._require_scene(project, scene_id).rename(name))

    def set_active_scene(self, project: StudioProject, scene_id: str) -> StudioProject:
        self._require_scene(project, scene_id)
        return project.with_scenes(list(project.scenes), active_scene_id=scene_id)

    def remove_scene(self, project: StudioProject, scene_id: str) -> StudioProject:
        self._require_scene(project, scene_id)
        scenes = [scene for scene in project.scenes if scene.scene_id != scene_id]
        if not scenes:
            raise ValueError("Project must contain at least one scene")
        active_scene_id = project.active_scene_id if project.active_scene_id != scene_id else scenes[0].scene_id
        return project.with_scenes(scenes, active_scene_id=active_scene_id)

    def add_source(self, project: StudioProject, scene_id: str, source: CaptureSource) -> StudioProject:
        return self._replace_scene(project, self._require_scene(project, scene_id).add_source(source))

    def duplicate_source(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        name: Optional[str] = None,
    ) -> StudioProject:
        scene = self._require_scene(project, scene_id)
        source = self._require_source(scene, source_id)
        duplicated = self._clone_source(source, name=name or f"{source.name} Copy")
        return self._replace_scene(project, scene.add_source(duplicated))

    def update_source(self, project: StudioProject, scene_id: str, source: CaptureSource) -> StudioProject:
        scene = self._require_scene(project, scene_id)
        self._require_source(scene, source.source_id)
        return self._replace_scene(project, scene.replace_source(source))

    def remove_source(self, project: StudioProject, scene_id: str, source_id: str) -> StudioProject:
        scene = self._require_scene(project, scene_id)
        self._require_source(scene, source_id)
        return self._replace_scene(project, scene.remove_source(source_id))

    def reorder_source(self, project: StudioProject, scene_id: str, source_id: str, z_index: int) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_z_index(z_index))

    def set_source_volume(self, project: StudioProject, scene_id: str, source_id: str, volume: float) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_volume(volume))

    def mute_source(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        muted: bool = True,
    ) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_muted(muted))

    def set_source_opacity(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        opacity: float,
    ) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_opacity(opacity))

    def enable_source(self, project: StudioProject, scene_id: str, source_id: str, enabled: bool) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_enabled(enabled))

    def set_source_visibility(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        visible: bool,
    ) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_transform(visible=visible))

    def lock_source(self, project: StudioProject, scene_id: str, source_id: str, locked: bool) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_transform(locked=locked))

    def set_source_transform(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        **changes,
    ) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_transform(**changes))

    def set_source_gain(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        gain_db: float,
    ) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_audio(gain_db=gain_db))

    def set_source_sync_offset(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        sync_offset_ms: int,
    ) -> StudioProject:
        return self._update_source(
            project,
            scene_id,
            source_id,
            lambda source: source.with_audio(sync_offset_ms=sync_offset_ms),
        )

    def solo_source(self, project: StudioProject, scene_id: str, source_id: str, solo: bool) -> StudioProject:
        return self._update_source(project, scene_id, source_id, lambda source: source.with_audio(solo=solo))

    def set_monitoring_mode(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        monitoring_mode: MonitoringMode,
    ) -> StudioProject:
        return self._update_source(
            project,
            scene_id,
            source_id,
            lambda source: source.with_audio(monitoring_mode=monitoring_mode),
        )

    def update_audio_levels(
        self,
        project: StudioProject,
        scene_id: str,
        source_id: str,
        peak_level: float,
        rms_level: float,
    ) -> StudioProject:
        return self._update_source(
            project,
            scene_id,
            source_id,
            lambda source: source.with_audio(peak_level=peak_level, rms_level=rms_level),
        )

    def replace_sources(self, project: StudioProject, scene_id: str, sources: list[CaptureSource]) -> StudioProject:
        return self._replace_scene(project, self._require_scene(project, scene_id).with_sources(sources))

    def build_legacy_scene(
        self,
        mode: str,
        rect: Optional[tuple[int, int, int, int]],
        mic: Optional[str],
        system: bool,
        window_title: str = "",
        window_hwnd: Optional[int] = None,
        display_index: int = 1,
        display_name: Optional[str] = None,
        display_bounds: Optional[tuple[int, int, int, int]] = None,
    ) -> Scene:
        video_source = self._create_video_source(
            mode,
            rect,
            window_title,
            window_hwnd,
            display_index,
            display_name,
            display_bounds,
        )
        sources = [video_source]
        if mic:
            sources.append(self.create_microphone_source(mic))
        if system:
            sources.append(self.create_system_audio_source())
        return self.create_scene("Live Scene").with_sources(sources)

    def create_display_source(
        self,
        name: Optional[str] = None,
        monitor_index: int = 1,
        monitor_name: Optional[str] = None,
        bounds: Optional[tuple[int, int, int, int]] = None,
    ) -> CaptureSource:
        source_name = name or monitor_name or f"Display {monitor_index}"
        metadata = {"monitor_index": monitor_index, "monitor_name": monitor_name or source_name}
        return self._create_source(
            name=source_name,
            kind=SourceKind.DISPLAY,
            bounds=Bounds.from_rect(bounds) if bounds else None,
            metadata=metadata,
        )

    def create_region_source(
        self,
        rect: tuple[int, int, int, int],
        name: str = "Region Capture",
        z_index: int = 0,
    ) -> CaptureSource:
        return self._create_source(name=name, kind=SourceKind.REGION, bounds=Bounds.from_rect(rect), z_index=z_index)

    def create_window_source(
        self,
        title: str,
        hwnd: Optional[int],
        rect: Optional[tuple[int, int, int, int]],
        z_index: int = 0,
    ) -> CaptureSource:
        metadata = {"hwnd": hwnd} if hwnd is not None else {}
        return self._create_source(
            name=title or "Window Capture",
            kind=SourceKind.WINDOW,
            bounds=Bounds.from_rect(rect) if rect else None,
            metadata=metadata,
            z_index=z_index,
        )

    def create_image_source(self, path: str, name: Optional[str] = None, z_index: int = 0) -> CaptureSource:
        return self._create_source(
            name=name or Path(path).name or "Image",
            kind=SourceKind.IMAGE,
            bounds=Bounds(x=0, y=0, width=1280, height=720),
            target=path,
            metadata={"path": path},
            z_index=z_index,
        )

    def create_text_source(
        self,
        text: str,
        name: str = "Text",
        color: str = "#FFFFFF",
        z_index: int = 0,
    ) -> CaptureSource:
        return self._create_source(
            name=name,
            kind=SourceKind.TEXT,
            bounds=Bounds(x=0, y=0, width=640, height=120),
            metadata={"text": text, "color": color},
            z_index=z_index,
        )

    def create_color_source(
        self,
        color: str,
        width: int = 320,
        height: int = 180,
        name: str = "Color Source",
        z_index: int = 0,
    ) -> CaptureSource:
        return self._create_source(
            name=name,
            kind=SourceKind.COLOR,
            bounds=Bounds(x=0, y=0, width=width, height=height),
            metadata={"color": color},
            z_index=z_index,
        )

    def create_media_source(self, path: str, name: Optional[str] = None, z_index: int = 0) -> CaptureSource:
        return self._create_source(
            name=name or Path(path).name or "Media",
            kind=SourceKind.MEDIA,
            bounds=Bounds(x=0, y=0, width=1280, height=720),
            target=path,
            metadata={"path": path, "preview_mode": "placeholder"},
            z_index=z_index,
        )

    def create_browser_source(
        self,
        url: str,
        width: int = 1280,
        height: int = 720,
        name: str = "Browser Source",
        refresh_policy: str = "manual",
        custom_css: str = "",
        transparent: bool = False,
        z_index: int = 0,
    ) -> CaptureSource:
        return self._create_source(
            name=name,
            kind=SourceKind.BROWSER,
            target=url,
            bounds=Bounds(x=0, y=0, width=width, height=height),
            metadata={
                "url": url,
                "refresh_policy": refresh_policy,
                "custom_css": custom_css,
                "transparent": transparent,
                "preview_status": "placeholder",
            },
            z_index=z_index,
        )

    def create_microphone_source(self, device_name: str) -> CaptureSource:
        return self._create_source(name=device_name, kind=SourceKind.MICROPHONE, target=device_name)

    def create_system_audio_source(self) -> CaptureSource:
        return self._create_source(name="System Audio", kind=SourceKind.SYSTEM_AUDIO)

    def _create_video_source(
        self,
        mode: str,
        rect: Optional[tuple[int, int, int, int]],
        window_title: str,
        window_hwnd: Optional[int],
        display_index: int,
        display_name: Optional[str],
        display_bounds: Optional[tuple[int, int, int, int]],
    ) -> CaptureSource:
        if mode == "screen":
            return self.create_display_source(
                monitor_index=display_index,
                monitor_name=display_name,
                bounds=display_bounds,
            )
        if mode == "window":
            return self.create_window_source(window_title, window_hwnd, rect)
        if rect is None:
            raise ValueError("Region capture requires bounds")
        return self.create_region_source(rect)

    def _replace_scene(self, project: StudioProject, scene: Scene) -> StudioProject:
        scenes = [item if item.scene_id != scene.scene_id else scene for item in project.scenes]
        return project.with_scenes(scenes)

    def _update_source(self, project: StudioProject, scene_id: str, source_id: str, updater) -> StudioProject:
        scene = self._require_scene(project, scene_id)
        source = self._require_source(scene, source_id)
        return self._replace_scene(project, scene.replace_source(updater(source)))

    def _require_scene(self, project: StudioProject, scene_id: str) -> Scene:
        scene = project.get_scene(scene_id)
        if scene is None:
            raise SceneNotFoundError(f"Scene not found: {scene_id}")
        return scene

    @staticmethod
    def _require_source(scene: Scene, source_id: str) -> CaptureSource:
        source = scene.get_source(source_id)
        if source is None:
            raise SourceNotFoundError(f"Source not found: {source_id}")
        return source

    def _clone_source(self, source: CaptureSource, name: Optional[str] = None) -> CaptureSource:
        return source.copy_with(source_id=self._id_factory(), name=name or source.name)

    def _create_source(
        self,
        name: str,
        kind: SourceKind,
        bounds: Optional[Bounds] = None,
        target: Optional[str] = None,
        metadata: Optional[dict] = None,
        z_index: int = 0,
    ) -> CaptureSource:
        return CaptureSource(
            source_id=self._id_factory(),
            name=name,
            kind=kind,
            bounds=bounds,
            target=target,
            metadata=dict(metadata or {}),
            z_index=z_index,
        )

    @staticmethod
    def _create_id() -> str:
        return uuid.uuid4().hex
