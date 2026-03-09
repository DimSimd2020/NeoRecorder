def load_modules(fresh_import):
    return fresh_import("core.studio.models"), fresh_import("gui.studio_presenter")


def test_format_source_kind_maps_known_values(fresh_import):
    models, presenter = load_modules(fresh_import)

    assert presenter.format_source_kind(models.SourceKind.DISPLAY) == "Display"
    assert presenter.format_source_kind(models.SourceKind.MICROPHONE) == "Microphone"


def test_format_bounds_formats_fullscreen_and_rect(fresh_import):
    models, presenter = load_modules(fresh_import)

    assert presenter.format_bounds(None) == "Fullscreen"
    assert presenter.format_bounds(models.Bounds(10, 20, 30, 40)) == "10,20 • 30x40"


def test_format_source_caption_formats_video_source(fresh_import):
    models, presenter = load_modules(fresh_import)
    source = models.CaptureSource(
        "1",
        "Display 2",
        models.SourceKind.DISPLAY,
        z_index=4,
        metadata={"monitor_index": 2, "monitor_name": "Display 2"},
    )

    assert presenter.format_source_caption(source) == "Display • D2 • Z4"


def test_format_source_caption_formats_audio_source(fresh_import):
    models, presenter = load_modules(fresh_import)
    source = models.CaptureSource("1", "Mic", models.SourceKind.MICROPHONE, volume=0.35)

    assert presenter.format_source_caption(source) == "Microphone • 35%"


def test_format_scene_summary_reports_counts(fresh_import):
    models, presenter = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Display", models.SourceKind.DISPLAY),
            models.CaptureSource("2", "Mic", models.SourceKind.MICROPHONE),
        ),
    )

    assert presenter.format_scene_summary(scene) == "2 sources • 1 video • 1 audio"


def test_format_preview_caption_reports_layer_counts(fresh_import):
    models, presenter = load_modules(fresh_import)
    scene = models.Scene(
        scene_id="scene",
        name="Main",
        sources=(
            models.CaptureSource("1", "Display", models.SourceKind.DISPLAY, z_index=0),
            models.CaptureSource(
                "2",
                "Overlay",
                models.SourceKind.REGION,
                bounds=models.Bounds(0, 0, 20, 20),
                z_index=5,
            ),
        ),
    )

    assert presenter.format_preview_caption(scene) == "2 layers • 1 overlays"
