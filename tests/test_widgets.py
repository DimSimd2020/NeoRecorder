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
