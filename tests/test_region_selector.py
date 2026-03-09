import types


def load_region_selector(fresh_import):
    return fresh_import("utils.region_selector")


class DisplayManagerStub:
    def __init__(self, bounds):
        self.bounds = bounds

    def get_virtual_bounds(self):
        return self.bounds


def test_region_selector_returns_absolute_rect(fresh_import, monkeypatch, fake_widget):
    selector_module = load_region_selector(fresh_import)
    display_module = fresh_import("utils.display_manager")
    monkeypatch.setattr(
        selector_module,
        "get_display_manager",
        lambda: DisplayManagerStub(display_module.DisplayBounds(left=-1280, top=0, width=3200, height=1080)),
    )
    selected = []

    selector = selector_module.RegionSelector(fake_widget, selected.append, lock_input=False)
    selector._on_press(types.SimpleNamespace(x=20, y=30))
    selector._on_release(types.SimpleNamespace(x=120, y=160))

    assert selected == [(-1260, 30, -1160, 160)]
    assert selector.window.geometry_value == "3200x1080-1280+0"


def test_region_selector_resets_too_small_selection(fresh_import, monkeypatch, fake_widget):
    selector_module = load_region_selector(fresh_import)
    display_module = fresh_import("utils.display_manager")
    monkeypatch.setattr(
        selector_module,
        "get_display_manager",
        lambda: DisplayManagerStub(display_module.DisplayBounds(left=0, top=0, width=1920, height=1080)),
    )
    selected = []

    selector = selector_module.RegionSelector(fake_widget, selected.append, lock_input=False)
    selector._on_press(types.SimpleNamespace(x=10, y=10))
    selector._on_release(types.SimpleNamespace(x=15, y=18))

    assert selected == []
    assert selector.start_x is None
