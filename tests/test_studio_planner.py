import pytest


def load_modules(fresh_import):
    return fresh_import("core.studio.models"), fresh_import("core.studio.planner")


def test_planner_builds_screen_request(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource(
                "1",
                "Display 2",
                models.SourceKind.DISPLAY,
                bounds=models.Bounds(x=-1280, y=0, width=1280, height=1024),
                metadata={"monitor_index": 2, "monitor_name": "Display 2"},
            ),
            models.CaptureSource("2", "Mic", models.SourceKind.MICROPHONE, target="USB Mic"),
            models.CaptureSource("3", "System", models.SourceKind.SYSTEM_AUDIO),
        ),
    )

    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert request.mode == "screen"
    assert request.rect == (-1280, 0, 0, 1024)
    assert request.mic == "USB Mic"
    assert request.system is True
    assert request.plan.primary_video.source_id == "1"


def test_planner_builds_region_request(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource(
                "1",
                "Region",
                models.SourceKind.REGION,
                bounds=models.Bounds(x=10, y=20, width=100, height=50),
            ),
        ),
    )

    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert request.mode == "region"
    assert request.rect == (10, 20, 110, 70)
    assert request.plan.primary_video.source_id == "1"


def test_planner_builds_window_request(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource(
                "1",
                "Window",
                models.SourceKind.WINDOW,
                bounds=models.Bounds(x=5, y=10, width=50, height=20),
            ),
        ),
    )

    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert request.mode == "window"
    assert request.rect == (5, 10, 55, 30)


def test_planner_returns_first_enabled_microphone(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Display", models.SourceKind.DISPLAY),
            models.CaptureSource("2", "Mic A", models.SourceKind.MICROPHONE, target="A"),
            models.CaptureSource("3", "Mic B", models.SourceKind.MICROPHONE, target="B"),
        ),
    )

    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert request.mic == "A"


def test_planner_returns_false_for_missing_system_audio(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(models.CaptureSource("1", "Display", models.SourceKind.DISPLAY),),
    )

    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert request.system is False


def test_planner_rejects_scene_without_video_source(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE, target="Mic"),),
    )

    with pytest.raises(Exception):
        planner_module.SceneRecordingPlanner().build_request(scene)


def test_planner_builds_composition_plan_for_multiple_video_sources(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Display", models.SourceKind.DISPLAY, z_index=0),
            models.CaptureSource(
                "2",
                "Region",
                models.SourceKind.REGION,
                bounds=models.Bounds(0, 0, 10, 10),
                z_index=5,
                opacity=0.7,
            ),
        ),
    )

    planner = planner_module.SceneRecordingPlanner()
    plan = planner.build_plan(scene)
    request = planner.build_request(scene)

    assert plan.primary_video.source_id == "1"
    assert len(plan.overlays) == 1
    assert plan.overlays[0].source_id == "2"
    assert plan.overlays[0].opacity == 0.7
    assert request.mode == "screen"


def test_planner_rejects_window_without_bounds(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(models.CaptureSource("1", "Window", models.SourceKind.WINDOW),),
    )

    with pytest.raises(Exception):
        planner_module.SceneRecordingPlanner().build_request(scene)


def test_planner_excludes_muted_audio_from_legacy_request(fresh_import):
    models, planner_module = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Display", models.SourceKind.DISPLAY),
            models.CaptureSource(
                "2",
                "Mic",
                models.SourceKind.MICROPHONE,
                target="USB Mic",
                muted=True,
            ),
            models.CaptureSource("3", "System", models.SourceKind.SYSTEM_AUDIO, muted=True),
        ),
    )

    plan = planner_module.SceneRecordingPlanner().build_plan(scene)
    request = planner_module.SceneRecordingPlanner().build_request(scene)

    assert len(plan.audio_channels) == 2
    assert request.mic is None
    assert request.system is False
