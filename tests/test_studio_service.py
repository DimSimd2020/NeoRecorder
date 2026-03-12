from pathlib import Path

import pytest


def load_modules(fresh_import):
    return fresh_import("core.studio.models"), fresh_import("core.studio.service")


def id_factory():
    counter = {"value": 0}

    def create():
        counter["value"] += 1
        return f"id-{counter['value']}"

    return create


def test_create_project_builds_default_scene(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    project = service.create_project("NeoRecorder")

    assert project.name == "NeoRecorder"
    assert len(project.scenes) == 1
    assert project.active_scene_id == project.scenes[0].scene_id


def test_create_scene_assigns_id(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    scene = service.create_scene("Gameplay")

    assert scene.scene_id == "id-1"
    assert scene.name == "Gameplay"


def test_save_and_load_project_roundtrip(fresh_import, tmp_path):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    path = tmp_path / "project.json"

    service.save_project(project, path)
    loaded = service.load_project(path)

    assert loaded == project


def test_add_scene_appends_new_scene(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")

    project = service.add_scene(project, "Camera")

    assert len(project.scenes) == 2
    assert project.scenes[-1].name == "Camera"


def test_rename_scene_updates_matching_scene(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    scene_id = project.active_scene_id

    project = service.rename_scene(project, scene_id, "Gameplay")

    assert project.active_scene().name == "Gameplay"


def test_set_active_scene_switches_scene(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    project = service.add_scene(project, "Second")

    updated = service.set_active_scene(project, project.scenes[1].scene_id)

    assert updated.active_scene_id == project.scenes[1].scene_id


def test_remove_scene_updates_active_scene_if_needed(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    project = service.add_scene(project, "Second")

    updated = service.remove_scene(project, project.active_scene_id)

    assert len(updated.scenes) == 1
    assert updated.active_scene_id == updated.scenes[0].scene_id


def test_remove_scene_rejects_last_scene(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")

    with pytest.raises(ValueError):
        service.remove_scene(project, project.active_scene_id)


def test_add_update_remove_source(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    scene_id = project.active_scene_id
    source = service.create_display_source()

    project = service.add_source(project, scene_id, source)
    renamed = models.CaptureSource(
        source_id=source.source_id,
        name="Display 2",
        kind=source.kind,
        enabled=source.enabled,
        bounds=source.bounds,
        target=source.target,
        metadata=source.metadata,
    )
    project = service.update_source(project, scene_id, renamed)
    project = service.remove_source(project, scene_id, source.source_id)

    assert project.active_scene().sources == ()


def test_duplicate_scene_clones_sources_with_new_ids(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_display_source()
    project = service.add_source(project, project.active_scene_id, source)

    duplicated = service.duplicate_scene(project, project.active_scene_id)

    assert len(duplicated.scenes) == 2
    assert duplicated.scenes[-1].scene_id != project.active_scene_id
    assert duplicated.scenes[-1].sources[0].source_id != source.source_id


def test_duplicate_source_adds_copy_with_new_id(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_display_source()
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.duplicate_source(project, project.active_scene_id, source.source_id)

    assert len(updated.active_scene().sources) == 2
    assert updated.active_scene().sources[-1].source_id != source.source_id


def test_replace_sources_swaps_scene_sources(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    sources = [service.create_display_source(), service.create_system_audio_source()]

    updated = service.replace_sources(project, project.active_scene_id, sources)

    assert len(updated.active_scene().sources) == 2


def test_create_display_source_builds_video_source(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    source = service.create_display_source(monitor_index=2, monitor_name="Display 2", bounds=(-1280, 0, 0, 1024))

    assert source.kind == models.SourceKind.DISPLAY
    assert source.display_index() == 2
    assert source.display_name() == "Display 2"
    assert source.bounds.to_rect() == (-1280, 0, 0, 1024)


def test_create_region_source_stores_bounds(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    source = service.create_region_source((10, 20, 50, 80), z_index=4)

    assert source.bounds.to_rect() == (10, 20, 50, 80)
    assert source.z_index == 4


def test_create_window_source_preserves_hwnd_metadata(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    source = service.create_window_source("Browser", 123, (10, 20, 110, 120), z_index=2)

    assert source.metadata["hwnd"] == 123
    assert source.bounds.to_rect() == (10, 20, 110, 120)
    assert source.z_index == 2


def test_create_microphone_source_sets_target(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    source = service.create_microphone_source("USB Mic")

    assert source.kind == models.SourceKind.MICROPHONE
    assert source.target == "USB Mic"


def test_create_system_audio_source_has_expected_name(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    source = service.create_system_audio_source()

    assert source.kind == models.SourceKind.SYSTEM_AUDIO
    assert source.name == "System Audio"


@pytest.mark.parametrize("mode", ["screen", "region", "window"])
def test_build_legacy_scene_creates_video_source_for_mode(fresh_import, mode):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    rect = (10, 20, 100, 120)

    scene = service.build_legacy_scene(
        mode=mode,
        rect=rect,
        mic="USB Mic",
        system=True,
        window_title="Browser",
        window_hwnd=100,
        display_index=2,
        display_name="Display 2",
        display_bounds=(-1280, 0, 0, 1024),
    )

    assert len(scene.sources) == 3
    if mode == "screen":
        assert scene.primary_video_source().display_index() == 2


def test_build_legacy_scene_requires_rect_for_region(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    with pytest.raises(ValueError):
        service.build_legacy_scene("region", None, None, False)


def test_service_raises_when_scene_missing(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")

    with pytest.raises(Exception):
        service.rename_scene(project, "missing", "Name")


def test_service_raises_when_source_missing(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")

    with pytest.raises(Exception):
        service.remove_source(project, project.active_scene_id, "missing")


def test_reorder_source_updates_z_index(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_display_source()
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.reorder_source(project, project.active_scene_id, source.source_id, 10)

    assert updated.active_scene().get_source(source.source_id).z_index == 10


def test_set_source_volume_updates_value(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_microphone_source("USB Mic")
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.set_source_volume(project, project.active_scene_id, source.source_id, 0.3)

    assert updated.active_scene().get_source(source.source_id).volume == 0.3


def test_mute_source_updates_flag(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_microphone_source("USB Mic")
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.mute_source(project, project.active_scene_id, source.source_id)

    assert updated.active_scene().get_source(source.source_id).muted is True


def test_set_source_opacity_updates_value(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_display_source()
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.set_source_opacity(project, project.active_scene_id, source.source_id, 0.5)

    assert updated.active_scene().get_source(source.source_id).opacity == 0.5


def test_enable_source_updates_flag(fresh_import):
    _models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_display_source()
    project = service.add_source(project, project.active_scene_id, source)

    updated = service.enable_source(project, project.active_scene_id, source.source_id, False)

    assert updated.active_scene().get_source(source.source_id).enabled is False


def test_visibility_lock_and_audio_settings_updates(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())
    project = service.create_project("NeoRecorder")
    source = service.create_microphone_source("USB Mic")
    project = service.add_source(project, project.active_scene_id, source)

    project = service.set_source_visibility(project, project.active_scene_id, source.source_id, False)
    project = service.lock_source(project, project.active_scene_id, source.source_id, True)
    project = service.set_source_gain(project, project.active_scene_id, source.source_id, 3.0)
    project = service.set_source_sync_offset(project, project.active_scene_id, source.source_id, 140)
    project = service.solo_source(project, project.active_scene_id, source.source_id, True)
    project = service.set_monitoring_mode(
        project,
        project.active_scene_id,
        source.source_id,
        models.MonitoringMode.MONITOR_ONLY,
    )
    project = service.update_audio_levels(project, project.active_scene_id, source.source_id, 0.7, 0.3)

    updated = project.active_scene().get_source(source.source_id)
    assert updated.transform.visible is False
    assert updated.transform.locked is True
    assert updated.audio.gain_db == 3.0
    assert updated.audio.sync_offset_ms == 140
    assert updated.audio.solo is True
    assert updated.audio.monitoring_mode == models.MonitoringMode.MONITOR_ONLY
    assert updated.audio.peak_level == 0.7


def test_create_new_source_kinds(fresh_import):
    models, service_module = load_modules(fresh_import)
    service = service_module.StudioProjectService(id_factory=id_factory())

    browser = service.create_browser_source("https://example.com")
    image = service.create_image_source("C:/tmp/hero.png")
    text = service.create_text_source("HELLO")
    color = service.create_color_source("#FF0000")
    media = service.create_media_source("C:/tmp/intro.mp4")

    assert browser.kind == models.SourceKind.BROWSER
    assert image.kind == models.SourceKind.IMAGE
    assert image.bounds.to_rect() == (0, 0, 1280, 720)
    assert text.metadata["text"] == "HELLO"
    assert text.bounds.to_rect() == (0, 0, 640, 120)
    assert color.metadata["color"] == "#FF0000"
    assert media.kind == models.SourceKind.MEDIA
    assert media.bounds.to_rect() == (0, 0, 1280, 720)
