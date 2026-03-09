def load_notifications(fresh_import):
    return fresh_import("utils.notifications")


def test_build_toast_payload_compacts_text(fresh_import):
    notifications = load_notifications(fresh_import)

    payload = notifications.build_toast_payload(
        "  Recording   saved  ",
        " line 1 \n\n line 2 ",
        kind=notifications.NotificationKind.SUCCESS,
        footer="  open folder  ",
    )

    assert payload.title == "Recording saved"
    assert payload.message == "line 1\nline 2"
    assert payload.footer == "open folder"
    assert payload.icon == "OK"


def test_compute_toast_geometry_positions_bottom_right(fresh_import):
    notifications = load_notifications(fresh_import)
    bounds = notifications.DisplayBounds(left=-1280, top=0, width=3200, height=1080)

    width, height, x, y = notifications.compute_toast_geometry(bounds, scale=1.0, line_count=4)

    assert (width, height) == (380, 154)
    assert x == 1514
    assert y == 852


def test_toast_line_count_counts_footer(fresh_import):
    notifications = load_notifications(fresh_import)
    payload = notifications.build_toast_payload("A", "one\ntwo", footer="footer")

    assert notifications.toast_line_count(payload) == 4


def test_legacy_toast_wrapper_schedules_notification(fresh_import):
    toast_module = fresh_import("gui.toast")
    calls = []

    class Master:
        def after(self, delay, callback):
            calls.append(delay)
            callback()

    toast_module.show_notification = lambda *args, **kwargs: calls.append((args, kwargs))
    toast_module.show_toast(Master(), "Title", "Message", duration=1500)

    assert calls[0] == 0
    assert calls[1][1]["duration"] == 1.5
