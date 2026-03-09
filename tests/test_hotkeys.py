import sys
import types


class KeyboardStub:
    def __init__(self):
        self.registered = []
        self.removed = []
        self.unhooked = False

    def add_hotkey(self, hotkey, callback, **kwargs):
        self.registered.append((hotkey, callback, kwargs))
        return len(self.registered)

    def remove_hotkey(self, hook_id):
        self.removed.append(hook_id)

    def unhook_all(self):
        self.unhooked = True


def load_hotkeys(fresh_import):
    return fresh_import("utils.hotkeys")


def test_register_returns_false_for_invalid_input(fresh_import):
    hotkeys = load_hotkeys(fresh_import)
    manager = hotkeys.HotkeyManager()

    assert manager.register("", lambda: None) is False
    assert manager.register("ctrl+s", None) is False


def test_ensure_keyboard_returns_false_when_module_missing(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    monkeypatch.setitem(sys.modules, "keyboard", None)
    manager = hotkeys.HotkeyManager()

    assert manager._ensure_keyboard() is False


def test_register_normalizes_hotkey_and_stores_mapping(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    keyboard = KeyboardStub()
    monkeypatch.setitem(sys.modules, "keyboard", keyboard)
    manager = hotkeys.HotkeyManager()

    result = manager.register("Ctrl + Shift + S", lambda: None, "quick_overlay")

    assert result is True
    assert keyboard.registered[0][0] == "ctrl+shift+s"
    assert manager.get_registered_hotkeys() == {"quick_overlay": "ctrl+shift+s"}


def test_register_replaces_existing_action_without_deadlock(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    keyboard = KeyboardStub()
    monkeypatch.setitem(sys.modules, "keyboard", keyboard)
    manager = hotkeys.HotkeyManager()
    manager.register("ctrl+s", lambda: None, "capture")

    result = manager.register("ctrl+r", lambda: None, "capture")

    assert result is True
    assert keyboard.removed == [1]
    assert manager.get_registered_hotkeys()["capture"] == "ctrl+r"


def test_unregister_removes_hotkey(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    keyboard = KeyboardStub()
    monkeypatch.setitem(sys.modules, "keyboard", keyboard)
    manager = hotkeys.HotkeyManager()
    manager.register("ctrl+s", lambda: None, "capture")

    assert manager.unregister("capture") is True
    assert manager.is_registered("capture") is False


def test_unregister_returns_false_for_missing_action(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    monkeypatch.setitem(sys.modules, "keyboard", KeyboardStub())
    manager = hotkeys.HotkeyManager()

    assert manager.unregister("missing") is False


def test_unregister_all_clears_state(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    keyboard = KeyboardStub()
    monkeypatch.setitem(sys.modules, "keyboard", keyboard)
    manager = hotkeys.HotkeyManager()
    manager.register("ctrl+s", lambda: None, "one")
    manager.register("ctrl+r", lambda: None, "two")

    manager.unregister_all()

    assert manager.get_registered_hotkeys() == {}
    assert manager._running is False
    assert keyboard.removed == [1, 2]


def test_stop_unhooks_all(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)
    keyboard = KeyboardStub()
    monkeypatch.setitem(sys.modules, "keyboard", keyboard)
    manager = hotkeys.HotkeyManager()
    manager.register("ctrl+s", lambda: None, "capture")

    manager.stop()

    assert keyboard.unhooked is True


def test_get_hotkey_manager_returns_singleton(fresh_import):
    hotkeys = load_hotkeys(fresh_import)

    assert hotkeys.get_hotkey_manager() is hotkeys.get_hotkey_manager()


def test_register_returns_false_when_keyboard_registration_fails(fresh_import, monkeypatch):
    hotkeys = load_hotkeys(fresh_import)

    class BrokenKeyboard(KeyboardStub):
        def add_hotkey(self, hotkey, callback, **kwargs):
            raise RuntimeError("broken")

    monkeypatch.setitem(sys.modules, "keyboard", BrokenKeyboard())
    manager = hotkeys.HotkeyManager()

    assert manager.register("ctrl+s", lambda: None, "capture") is False
