def load_window_finder(fresh_import):
    return fresh_import("core.window_finder")


def test_get_active_windows_filters_invisible_and_system_titles(fresh_import, monkeypatch):
    window_finder = load_window_finder(fresh_import)
    handles = [1, 2, 3, 4]
    visible = {1: True, 2: False, 3: True, 4: True}
    titles = {1: "NeoRecorder", 2: "Hidden", 3: "Program Manager", 4: ""}

    monkeypatch.setattr(
        window_finder.win32gui,
        "EnumWindows",
        lambda handler, ctx: [handler(hwnd, ctx) for hwnd in handles],
    )
    monkeypatch.setattr(window_finder.win32gui, "IsWindowVisible", lambda hwnd: visible[hwnd])
    monkeypatch.setattr(window_finder.win32gui, "GetWindowText", lambda hwnd: titles[hwnd])

    result = window_finder.WindowFinder.get_active_windows()

    assert result == [{"hwnd": 1, "title": "NeoRecorder"}]


def test_get_active_windows_collects_multiple_entries(fresh_import, monkeypatch):
    window_finder = load_window_finder(fresh_import)
    titles = {10: "App A", 20: "App B"}

    monkeypatch.setattr(
        window_finder.win32gui,
        "EnumWindows",
        lambda handler, ctx: [handler(hwnd, ctx) for hwnd in titles],
    )
    monkeypatch.setattr(window_finder.win32gui, "IsWindowVisible", lambda _hwnd: True)
    monkeypatch.setattr(window_finder.win32gui, "GetWindowText", lambda hwnd: titles[hwnd])

    result = window_finder.WindowFinder.get_active_windows()

    assert result == [{"hwnd": 10, "title": "App A"}, {"hwnd": 20, "title": "App B"}]


def test_get_window_rect_returns_coordinates(fresh_import, monkeypatch):
    window_finder = load_window_finder(fresh_import)
    monkeypatch.setattr(window_finder.win32gui, "GetWindowRect", lambda hwnd: (1, 2, 3, 4))

    assert window_finder.WindowFinder.get_window_rect(10) == (1, 2, 3, 4)


def test_get_window_rect_returns_none_on_error(fresh_import, monkeypatch):
    window_finder = load_window_finder(fresh_import)
    monkeypatch.setattr(
        window_finder.win32gui,
        "GetWindowRect",
        lambda hwnd: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert window_finder.WindowFinder.get_window_rect(10) is None
