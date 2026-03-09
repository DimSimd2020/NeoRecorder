import pytest


def load_models(fresh_import):
    return fresh_import("core.studio.models")


def test_source_kind_audio_flags(fresh_import):
    models = load_models(fresh_import)

    assert models.SourceKind.MICROPHONE.is_audio() is True
    assert models.SourceKind.DISPLAY.is_video() is True


def test_bounds_from_rect_normalizes_coordinates(fresh_import):
    models = load_models(fresh_import)

    bounds = models.Bounds.from_rect((20, 30, 10, 5))

    assert bounds.to_rect() == (10, 5, 20, 30)


@pytest.mark.parametrize(("width", "height"), [(0, 10), (10, 0), (-1, 10)])
def test_bounds_rejects_non_positive_dimensions(fresh_import, width, height):
    models = load_models(fresh_import)

    with pytest.raises(ValueError):
        models.Bounds(x=0, y=0, width=width, height=height)


def test_bounds_to_from_dict_roundtrip(fresh_import):
    models = load_models(fresh_import)
    bounds = models.Bounds(x=1, y=2, width=3, height=4)

    restored = models.Bounds.from_dict(bounds.to_dict())

    assert restored == bounds


def test_capture_source_with_enabled_returns_copy(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE)

    updated = source.with_enabled(False)

    assert updated.enabled is False
    assert source.enabled is True


@pytest.mark.parametrize("volume", [-0.1, 1.1])
def test_capture_source_rejects_invalid_volume(fresh_import, volume):
    models = load_models(fresh_import)

    with pytest.raises(ValueError):
        models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE, volume=volume)


@pytest.mark.parametrize("opacity", [-0.1, 1.1])
def test_capture_source_rejects_invalid_opacity(fresh_import, opacity):
    models = load_models(fresh_import)

    with pytest.raises(ValueError):
        models.CaptureSource("1", "Display", models.SourceKind.DISPLAY, opacity=opacity)


def test_capture_source_serialization_roundtrip(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource(
        source_id="1",
        name="Window",
        kind=models.SourceKind.WINDOW,
        bounds=models.Bounds(x=10, y=20, width=100, height=80),
        metadata={"hwnd": 123},
        z_index=3,
        volume=0.5,
        muted=True,
        opacity=0.8,
    )

    restored = models.CaptureSource.from_dict(source.to_dict())

    assert restored == source


def test_capture_source_state_mutators_return_copies(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE)

    updated = source.with_z_index(5).with_volume(0.3).with_muted(True).with_opacity(0.6)

    assert updated.z_index == 5
    assert updated.volume == 0.3
    assert updated.muted is True
    assert updated.opacity == 0.6
    assert source.z_index == 0


def test_capture_source_display_metadata_helpers(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource(
        "1",
        "Display 2",
        models.SourceKind.DISPLAY,
        metadata={"monitor_index": 2, "monitor_name": "Display 2"},
    )

    assert source.display_index() == 2
    assert source.display_name() == "Display 2"


def test_capture_source_is_mixed_audio_respects_muted_and_volume(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE, volume=0.0)

    assert source.is_mixed_audio() is False
    assert source.with_volume(0.5).with_muted(False).is_mixed_audio() is True


def test_scene_get_source_returns_matching_item(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource("1", "Display", models.SourceKind.DISPLAY)
    scene = models.Scene(scene_id="scene", name="Main", sources=(source,))

    assert scene.get_source("1") == source


def test_scene_enabled_sources_filters_disabled_entries(fresh_import):
    models = load_models(fresh_import)
    enabled = models.CaptureSource("1", "Display", models.SourceKind.DISPLAY)
    disabled = models.CaptureSource("2", "Mic", models.SourceKind.MICROPHONE, enabled=False)
    scene = models.Scene(scene_id="scene", name="Main", sources=(enabled, disabled))

    assert scene.enabled_sources() == (enabled,)


def test_scene_audio_and_video_sources_split_types(fresh_import):
    models = load_models(fresh_import)
    display = models.CaptureSource("1", "Display", models.SourceKind.DISPLAY, z_index=10)
    region = models.CaptureSource(
        "3",
        "Region",
        models.SourceKind.REGION,
        bounds=models.Bounds(0, 0, 10, 10),
        z_index=1,
    )
    mic = models.CaptureSource("2", "Mic", models.SourceKind.MICROPHONE)
    scene = models.Scene(scene_id="scene", name="Main", sources=(display, mic))
    ordered_scene = models.Scene(scene_id="scene2", name="Ordered", sources=(display, region, mic))

    assert scene.video_sources() == (display,)
    assert scene.audio_sources() == (mic,)
    assert ordered_scene.video_sources() == (region, display)


def test_scene_mixed_audio_sources_excludes_muted_and_zero_volume(fresh_import):
    models = load_models(fresh_import)
    enabled = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE, volume=0.7)
    muted = models.CaptureSource("2", "Mic 2", models.SourceKind.MICROPHONE, muted=True)
    silent = models.CaptureSource("3", "Mic 3", models.SourceKind.MICROPHONE, volume=0.0)
    scene = models.Scene(scene_id="scene", name="Main", sources=(enabled, muted, silent))

    assert scene.mixed_audio_sources() == (enabled,)


def test_scene_primary_and_overlay_video_sources(fresh_import):
    models = load_models(fresh_import)
    base = models.CaptureSource("1", "Base", models.SourceKind.DISPLAY, z_index=0)
    overlay = models.CaptureSource(
        "2",
        "Overlay",
        models.SourceKind.REGION,
        bounds=models.Bounds(10, 10, 20, 20),
        z_index=5,
    )
    scene = models.Scene(scene_id="scene", name="Main", sources=(overlay, base))

    assert scene.primary_video_source() == base
    assert scene.overlay_video_sources() == (overlay,)


def test_scene_add_replace_remove_source(fresh_import):
    models = load_models(fresh_import)
    display = models.CaptureSource("1", "Display", models.SourceKind.DISPLAY)
    renamed = models.CaptureSource("1", "Display 2", models.SourceKind.DISPLAY)
    scene = models.Scene(scene_id="scene", name="Main")

    scene = scene.add_source(display)
    scene = scene.replace_source(renamed)
    scene = scene.remove_source("1")

    assert scene.sources == ()


def test_scene_rename_returns_new_instance(fresh_import):
    models = load_models(fresh_import)
    scene = models.Scene(scene_id="scene", name="Main")

    renamed = scene.rename("Gameplay")

    assert renamed.name == "Gameplay"
    assert scene.name == "Main"


def test_scene_serialization_roundtrip(fresh_import):
    models = load_models(fresh_import)
    source = models.CaptureSource("1", "Display", models.SourceKind.DISPLAY)
    scene = models.Scene(scene_id="scene", name="Main", sources=(source,))

    restored = models.Scene.from_dict(scene.to_dict())

    assert restored == scene


def test_project_active_scene_returns_selected_scene(fresh_import):
    models = load_models(fresh_import)
    scene = models.Scene(scene_id="scene", name="Main")
    project = models.StudioProject(
        project_id="project",
        name="NeoRecorder",
        scenes=(scene,),
        active_scene_id="scene",
    )

    assert project.active_scene() == scene


def test_project_get_scene_returns_none_for_missing_scene(fresh_import):
    models = load_models(fresh_import)
    scene = models.Scene(scene_id="scene", name="Main")
    project = models.StudioProject(
        project_id="project",
        name="NeoRecorder",
        scenes=(scene,),
        active_scene_id="scene",
    )

    assert project.get_scene("missing") is None


def test_project_with_scenes_updates_active_scene_when_provided(fresh_import):
    models = load_models(fresh_import)
    first = models.Scene(scene_id="one", name="One")
    second = models.Scene(scene_id="two", name="Two")
    project = models.StudioProject(
        project_id="project",
        name="NeoRecorder",
        scenes=(first,),
        active_scene_id="one",
    )

    updated = project.with_scenes([first, second], active_scene_id="two")

    assert updated.active_scene_id == "two"


def test_project_rename_returns_new_instance(fresh_import):
    models = load_models(fresh_import)
    scene = models.Scene(scene_id="scene", name="Main")
    project = models.StudioProject(
        project_id="project",
        name="Old",
        scenes=(scene,),
        active_scene_id="scene",
    )

    renamed = project.rename("New")

    assert renamed.name == "New"
    assert project.name == "Old"


def test_project_serialization_roundtrip(fresh_import):
    models = load_models(fresh_import)
    scene = models.Scene(scene_id="scene", name="Main")
    project = models.StudioProject(
        project_id="project",
        name="NeoRecorder",
        scenes=(scene,),
        active_scene_id="scene",
    )

    restored = models.StudioProject.from_dict(project.to_dict())

    assert restored == project
