def load_modules(fresh_import):
    return fresh_import("core.studio.models"), fresh_import("gui.widgets")


def test_scene_preview_scene_bounds_include_negative_coordinates(fresh_import):
    models, widgets = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource(
                "1",
                "Left Display",
                models.SourceKind.DISPLAY,
                bounds=models.Bounds(-1280, 0, 1280, 1024),
            ),
            models.CaptureSource(
                "2",
                "Overlay",
                models.SourceKind.REGION,
                bounds=models.Bounds(100, 50, 300, 200),
                z_index=2,
            ),
        ),
    )

    assert widgets.ScenePreview._scene_bounds(scene) == (-1280, 0, 400, 1024)


def test_scene_preview_resolves_rect_relative_to_scene_bounds(fresh_import, fake_widget):
    models, widgets = load_modules(fresh_import)
    preview = widgets.ScenePreview(fake_widget, width=320, height=250)
    source = models.CaptureSource(
        "1",
        "Left Display",
        models.SourceKind.DISPLAY,
        bounds=models.Bounds(-1280, 0, 1280, 1024),
    )

    rect = preview._resolve_rect(0, source, (-1280, 0, 400, 1024))

    assert rect[0] >= 44
    assert rect[1] >= 58
    assert rect[2] > rect[0]
    assert rect[3] > rect[1]


def test_scene_preview_render_draws_multiple_layers(fresh_import, fake_widget):
    models, widgets = load_modules(fresh_import)
    preview = widgets.ScenePreview(fake_widget, width=320, height=250)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Base", models.SourceKind.DISPLAY, bounds=models.Bounds(0, 0, 1920, 1080)),
            models.CaptureSource("2", "Overlay", models.SourceKind.REGION, bounds=models.Bounds(100, 100, 320, 180), z_index=2),
        ),
    )

    preview.render(scene)

    assert len(preview.canvas.items) >= 7


def test_scene_preview_respects_transform_crop_and_scale(fresh_import, fake_widget):
    models, widgets = load_modules(fresh_import)
    preview = widgets.ScenePreview(fake_widget, width=320, height=250)
    source = models.CaptureSource(
        "1",
        "Overlay",
        models.SourceKind.IMAGE,
        bounds=models.Bounds(0, 0, 200, 100),
    ).with_transform(
        position_x=20,
        position_y=10,
        scale_x=1.5,
        scale_y=2.0,
        crop=models.Crop(left=10, top=5, right=20, bottom=5),
        rotation_deg=15,
        locked=True,
    )

    rect = preview._source_rect(source, (0, 0, 1920, 1080))

    assert rect == (30, 15, 285, 195)


def test_mixer_strip_renders_audio_info(fresh_import, fake_widget):
    models, widgets = load_modules(fresh_import)
    source = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE).with_audio(
        gain_db=3.0,
        sync_offset_ms=120,
        solo=True,
        peak_level=0.6,
        rms_level=0.3,
        monitoring_mode=models.MonitoringMode.MONITOR_ONLY,
    )

    strip = widgets.MixerStrip(fake_widget, source, on_volume=lambda *_: None, on_mute=lambda *_: None, on_solo=lambda *_: None)

    assert strip._info_text() == "Gain +3.0dB • Sync 120ms • Monitor Only"


def test_scene_preview_exposes_preview_shell_metadata(fresh_import, fake_widget):
    models, widgets = load_modules(fresh_import)
    preview = widgets.ScenePreview(fake_widget, width=320, height=250)
    browser = models.CaptureSource(
        "1",
        "Browser",
        models.SourceKind.BROWSER,
        bounds=models.Bounds(0, 0, 1280, 720),
        metadata={"url": "https://example.com"},
    )

    preview.render(models.Scene(scene_id="scene", name="Main", sources=(browser,)))

    texts = [item["config"].get("text") for item in preview.canvas.items.values() if item["kind"] == "text"]
    assert "https://example.com" in texts
