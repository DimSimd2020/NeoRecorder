import types
from pathlib import Path


class MSSShot:
    def __init__(self, size=(10, 10), bgra=b"\x00" * 16):
        self.size = size
        self.bgra = bgra


class MSSStub:
    def __init__(self):
        self.monitors = [
            {"left": -1280, "top": 0, "width": 1380, "height": 100},
            {"left": 0, "top": 0, "width": 100, "height": 100},
            {"left": -1280, "top": 0, "width": 1280, "height": 100},
        ]
        self.grabs = []
        self.closed = False

    def grab(self, monitor):
        self.grabs.append(monitor)
        return MSSShot()

    def close(self):
        self.closed = True


def load_screenshot(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return fresh_import("utils.screenshot")


def test_capture_initializes_output_dir(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)

    capture = screenshot_module.ScreenshotCapture()

    assert Path(capture.get_output_dir()).exists()


def test_get_mss_is_lazy_singleton(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()

    assert capture._get_mss() is capture._get_mss()


def test_capture_fullscreen_saves_file(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()

    result = capture.capture_fullscreen()

    assert Path(result).exists()
    assert stub.grabs[0] == {"left": 0, "top": 0, "width": 100, "height": 100}


def test_capture_display_uses_selected_monitor(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()

    result = capture.capture_display(2)

    assert Path(result).exists()
    assert stub.grabs[0] == {"left": -1280, "top": 0, "width": 1280, "height": 100}


def test_capture_fullscreen_returns_none_on_error(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)

    class BrokenMSS(MSSStub):
        def grab(self, monitor):
            raise RuntimeError("boom")

    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: BrokenMSS())
    capture = screenshot_module.ScreenshotCapture()

    assert capture.capture_fullscreen() is None


def test_capture_region_normalizes_coordinates(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()

    result = capture.capture_region((20, 30, 5, 10))

    assert Path(result).exists()
    assert stub.grabs[0] == {"left": 5, "top": 10, "width": 15, "height": 20}


def test_capture_region_returns_none_for_zero_size(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    capture = screenshot_module.ScreenshotCapture()

    assert capture.capture_region((1, 1, 1, 10)) is None


def test_capture_to_clipboard_uses_fullscreen_when_rect_missing(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    copied = []
    capture = screenshot_module.ScreenshotCapture()
    monkeypatch.setattr(capture, "_copy_image_to_clipboard", lambda image: copied.append(image))

    assert capture.capture_to_clipboard() is True
    assert copied
    assert stub.grabs[0] == {"left": 0, "top": 0, "width": 100, "height": 100}


def test_capture_to_clipboard_uses_display_when_requested(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()
    monkeypatch.setattr(capture, "_copy_image_to_clipboard", lambda image: None)

    assert capture.capture_to_clipboard(monitor_index=2) is True
    assert stub.grabs[0] == {"left": -1280, "top": 0, "width": 1280, "height": 100}


def test_capture_to_clipboard_uses_region_when_provided(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()
    monkeypatch.setattr(capture, "_copy_image_to_clipboard", lambda image: None)

    assert capture.capture_to_clipboard((10, 20, 30, 50)) is True
    assert stub.grabs[0] == {"left": 10, "top": 20, "width": 20, "height": 30}


def test_capture_to_clipboard_returns_false_on_error(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)

    class BrokenMSS(MSSStub):
        def grab(self, monitor):
            raise RuntimeError("boom")

    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: BrokenMSS())
    capture = screenshot_module.ScreenshotCapture()

    assert capture.capture_to_clipboard() is False


def test_copy_image_to_clipboard_uses_windows_api(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    capture = screenshot_module.ScreenshotCapture()
    calls = []

    kernel32 = types.SimpleNamespace(
        GlobalAlloc=lambda flag, size: calls.append(("alloc", size)) or 10,
        GlobalLock=lambda handle: calls.append(("lock", handle)) or 20,
        GlobalUnlock=lambda handle: calls.append(("unlock", handle)),
    )
    user32 = types.SimpleNamespace(
        OpenClipboard=lambda value: calls.append(("open", value)),
        EmptyClipboard=lambda: calls.append(("empty", None)),
        SetClipboardData=lambda fmt, handle: calls.append(("set", fmt, handle)),
        CloseClipboard=lambda: calls.append(("close", None)),
    )
    monkeypatch.setattr(screenshot_module.ctypes, "windll", types.SimpleNamespace(kernel32=kernel32, user32=user32))
    monkeypatch.setattr(screenshot_module.ctypes, "memmove", lambda dst, src, size: calls.append(("memmove", size)))

    capture._copy_image_to_clipboard(screenshot_module.Image.new("RGB", (10, 10)))

    assert ("set", 8, 10) in calls


def test_set_output_dir_accepts_existing_or_new_directory(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    capture = screenshot_module.ScreenshotCapture()
    new_dir = tmp_path / "shots"

    capture.set_output_dir(str(new_dir))

    assert capture.get_output_dir() == str(new_dir)
    assert new_dir.exists()


def test_cleanup_closes_mss_instance(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)
    stub = MSSStub()
    monkeypatch.setattr(screenshot_module.mss, "mss", lambda: stub)
    capture = screenshot_module.ScreenshotCapture()
    capture._get_mss()

    capture.cleanup()

    assert stub.closed is True
    assert capture._sct is None


def test_get_screenshot_capture_returns_singleton(fresh_import, monkeypatch, tmp_path):
    screenshot_module = load_screenshot(fresh_import, monkeypatch, tmp_path)

    assert screenshot_module.get_screenshot_capture() is screenshot_module.get_screenshot_capture()
