import types


def load_quick_overlay(fresh_import):
    return fresh_import("gui.quick_overlay")


class DisplayManagerStub:
    def __init__(self, bounds):
        self.bounds = bounds

    def get_virtual_bounds(self):
        return self.bounds


def test_quick_overlay_returns_absolute_rect_for_screenshot(fresh_import, monkeypatch, fake_widget):
    overlay_module = load_quick_overlay(fresh_import)
    display_module = fresh_import("utils.display_manager")
    monkeypatch.setattr(
        overlay_module,
        "get_display_manager",
        lambda: DisplayManagerStub(display_module.DisplayBounds(left=-1280, top=0, width=3200, height=1080)),
    )
    shots = []
    records = []

    overlay = overlay_module.QuickOverlay(fake_widget, shots.append, records.append)
    overlay._on_press(types.SimpleNamespace(x=50, y=60))
    overlay._on_release(types.SimpleNamespace(x=150, y=180))

    assert shots == [(-1230, 60, -1130, 180)]
    assert records == []
    assert overlay.selection_win.geometry_value == "3200x1080-1280+0"


def test_quick_overlay_routes_record_mode(fresh_import, monkeypatch, fake_widget):
    overlay_module = load_quick_overlay(fresh_import)
    display_module = fresh_import("utils.display_manager")
    monkeypatch.setattr(
        overlay_module,
        "get_display_manager",
        lambda: DisplayManagerStub(display_module.DisplayBounds(left=0, top=-200, width=1920, height=1280)),
    )
    shots = []
    records = []

    overlay = overlay_module.QuickOverlay(fake_widget, shots.append, records.append)
    overlay._mode_record()
    overlay._on_press(types.SimpleNamespace(x=10, y=20))
    overlay._on_release(types.SimpleNamespace(x=50, y=80))

    assert shots == []
    assert records == [(10, -180, 50, -120)]
