def load_display_manager(fresh_import):
    return fresh_import("utils.display_manager")


class MSSStub:
    def __init__(self, monitors):
        self.monitors = monitors
        self.closed = False

    def close(self):
        self.closed = True


def test_list_monitors_maps_mss_layout(fresh_import):
    display_module = load_display_manager(fresh_import)
    stub = MSSStub(
        [
            {"left": -1280, "top": 0, "width": 3200, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": -1280, "top": 0, "width": 1280, "height": 1024},
        ]
    )
    manager = display_module.DisplayManager(mss_factory=lambda: stub)

    monitors = manager.list_monitors()

    assert len(monitors) == 2
    assert monitors[0].is_primary is True
    assert monitors[1].bounds.left == -1280
    assert monitors[1].to_label() == "Display 2 • 1280x1024 • -1280,0"
    assert stub.closed is True


def test_get_virtual_bounds_returns_root_monitor(fresh_import):
    display_module = load_display_manager(fresh_import)
    manager = display_module.DisplayManager(
        mss_factory=lambda: MSSStub(
            [
                {"left": -1280, "top": -200, "width": 4480, "height": 1640},
                {"left": 0, "top": 0, "width": 1920, "height": 1080},
            ]
        )
    )

    bounds = manager.get_virtual_bounds()

    assert bounds.to_rect() == (-1280, -200, 3200, 1440)
    assert bounds.to_geometry() == "4480x1640-1280-200"


def test_get_monitor_falls_back_to_primary(fresh_import):
    display_module = load_display_manager(fresh_import)
    manager = display_module.DisplayManager(
        mss_factory=lambda: MSSStub(
            [
                {"left": 0, "top": 0, "width": 1920, "height": 1080},
                {"left": 0, "top": 0, "width": 1920, "height": 1080},
            ]
        )
    )

    monitor = manager.get_monitor(5)

    assert monitor.index == 1
