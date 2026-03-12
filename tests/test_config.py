import json
import sys
from pathlib import Path

import pytest


def load_config(fresh_import, monkeypatch, tmp_path, exists=None):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    if exists is not None:
        monkeypatch.setattr("os.path.exists", exists)
    return fresh_import("config")


def test_resource_path_uses_current_directory(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    result = config.resource_path("assets/icon.png")

    assert result.endswith("assets/icon.png")


def test_resource_path_uses_meipass_when_present(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    config = load_config(fresh_import, monkeypatch, tmp_path)

    result = config.resource_path("file.txt")

    assert result == str(tmp_path / "file.txt")


@pytest.mark.parametrize(
    ("bundled_exists", "exe_exists", "expected"),
    [
        (True, False, "bundled"),
        (False, True, "exe"),
        (False, False, "fallback"),
    ],
)
def test_ffmpeg_path_detection(
    fresh_import,
    monkeypatch,
    tmp_path,
    bundled_exists,
    exe_exists,
    expected,
):
    executable = tmp_path / "NeoRecorder.exe"
    monkeypatch.setattr(sys, "executable", str(executable), raising=False)
    monkeypatch.setattr(sys, "frozen", expected == "exe", raising=False)

    def fake_exists(path):
        if str(path).endswith("assets"):
            return False
        if str(path) == str(tmp_path / "ffmpeg.exe"):
            return exe_exists
        if str(path).endswith("ffmpeg.exe"):
            return bundled_exists
        return False

    config = load_config(fresh_import, monkeypatch, tmp_path, exists=fake_exists)
    bundled_path = config.resource_path("ffmpeg.exe")
    exe_path = str(tmp_path / "ffmpeg.exe")

    if expected == "bundled":
        assert config.FFMPEG_PATH == bundled_path
    elif expected == "exe":
        assert config.FFMPEG_PATH == exe_path
    else:
        assert config.FFMPEG_PATH == "ffmpeg"


def test_settings_loads_defaults_when_file_missing(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert config.settings.get("fps") == config.DEFAULT_FPS
    assert config.settings.get_hotkey("quick_overlay") == "ctrl+shift+s"
    assert str(config.OUTPUT_SESSION_REPORT_FILE).endswith("runtime\\last_output_session.json")


def test_settings_merges_saved_values(fresh_import, monkeypatch, tmp_path):
    settings_dir = tmp_path / "Videos" / "NeoRecorder"
    settings_dir.mkdir(parents=True)
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(
        json.dumps({"fps": 144, "hotkeys": {"show_window": "alt+r"}}),
        encoding="utf-8",
    )

    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert config.settings.get("fps") == 144
    assert config.settings.get_hotkey("show_window") == "alt+r"
    assert config.settings.get_hotkey("quick_overlay") == "ctrl+shift+s"


def test_settings_load_handles_invalid_json(capsys, fresh_import, monkeypatch, tmp_path):
    settings_dir = tmp_path / "Videos" / "NeoRecorder"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.json").write_text("{broken", encoding="utf-8")

    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert config.settings.get("language") == config.DEFAULT_LANG
    assert "Error loading settings" in capsys.readouterr().out


def test_settings_save_writes_json(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    config.settings.set("fps", 120)

    payload = json.loads(Path(config.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert payload["fps"] == 120


def test_settings_get_returns_default_for_missing_key(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert config.settings.get("missing", "fallback") == "fallback"


def test_settings_set_hotkey_creates_section(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)
    config.settings._data.pop("hotkeys")

    config.settings.set_hotkey("start_recording", "ctrl+alt+r")

    assert config.settings.get_hotkey("start_recording") == "ctrl+alt+r"


def test_settings_all_returns_deep_copy(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    snapshot = config.settings.all
    snapshot["hotkeys"]["quick_overlay"] = "changed"

    assert config.settings.get_hotkey("quick_overlay") == "ctrl+shift+s"


def test_settings_singleton_returns_same_instance(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert config.Settings() is config.settings


def test_settings_preserves_default_hotkeys_after_mutation(fresh_import, monkeypatch, tmp_path):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    config.settings.set_hotkey("quick_overlay", "alt+s")
    fresh = config.Settings()

    assert config.DEFAULT_HOTKEYS["quick_overlay"] == "ctrl+shift+s"
    assert fresh.get_hotkey("quick_overlay") == "alt+s"


@pytest.mark.parametrize("fps", [30, 60, 120, 144, 240])
def test_fps_options_contain_supported_values(fresh_import, monkeypatch, tmp_path, fps):
    config = load_config(fresh_import, monkeypatch, tmp_path)

    assert fps in config.FPS_OPTIONS
