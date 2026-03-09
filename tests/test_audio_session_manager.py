import sys
import types

import pytest


class VolumeStub:
    def __init__(self, volume=0.5, muted=False):
        self.volume = volume
        self.muted = muted
        self.mute_calls = []
        self.volume_calls = []

    def GetMasterVolume(self):
        return self.volume

    def GetMute(self):
        return self.muted

    def SetMute(self, mute, _ctx):
        self.mute_calls.append(mute)

    def SetMasterVolume(self, volume, _ctx):
        self.volume_calls.append(volume)


class ProcessStub:
    def __init__(self, name, pid):
        self._name = name
        self.pid = pid

    def name(self):
        return self._name


class SessionStub:
    def __init__(self, name="app.exe", pid=10, volume=0.4, muted=False, process=True):
        self.Process = ProcessStub(name, pid) if process else None
        self.volume_stub = VolumeStub(volume, muted)
        self._ctl = self

    def QueryInterface(self, _interface):
        return self.volume_stub


def install_pycaw(monkeypatch, sessions):
    pycaw_package = types.ModuleType("pycaw")
    pycaw_module = types.ModuleType("pycaw.pycaw")
    pycaw_module.AudioUtilities = types.SimpleNamespace(
        GetAllSessions=lambda: sessions,
        GetSpeakers=lambda: object(),
    )
    pycaw_module.ISimpleAudioVolume = object()
    monkeypatch.setitem(sys.modules, "pycaw", pycaw_package)
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", pycaw_module)
    monkeypatch.setitem(sys.modules, "comtypes", types.SimpleNamespace(CLSCTX_ALL=1))


def load_manager(fresh_import):
    return fresh_import("core.audio_session_manager")


def test_check_pycaw_returns_false_when_module_missing(fresh_import, monkeypatch):
    manager_module = load_manager(fresh_import)
    monkeypatch.setattr(manager_module.AudioSessionManager, "_check_pycaw", lambda self: False)
    manager = manager_module.AudioSessionManager()

    assert manager._pycaw_available is False


def test_get_active_audio_sessions_returns_empty_when_unavailable(fresh_import, monkeypatch):
    manager_module = load_manager(fresh_import)
    monkeypatch.setattr(manager_module.AudioSessionManager, "_check_pycaw", lambda self: False)
    manager = manager_module.AudioSessionManager()

    assert manager.get_active_audio_sessions() == []


def test_get_active_audio_sessions_builds_domain_objects(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [SessionStub("obs.exe", 101, 0.7, True)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    sessions = manager.get_active_audio_sessions()

    assert len(sessions) == 1
    assert sessions[0].name == "obs.exe"
    assert sessions[0].pid == 101
    assert sessions[0].muted is True


def test_get_active_audio_sessions_skips_sessions_without_process(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [SessionStub(process=False)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.get_active_audio_sessions() == []


def test_get_active_audio_sessions_ignores_broken_session(fresh_import, monkeypatch):
    broken = SessionStub("broken.exe", 1)
    broken.QueryInterface = lambda _iface: (_ for _ in ()).throw(RuntimeError("no volume"))
    install_pycaw(monkeypatch, [broken, SessionStub("ok.exe", 2)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    sessions = manager.get_active_audio_sessions()

    assert [session.name for session in sessions] == ["ok.exe"]


def test_get_session_names_returns_unique_values(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [SessionStub("obs.exe", 1), SessionStub("obs.exe", 2)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.get_session_names() == ["obs.exe"]


def test_mute_session_returns_false_when_unavailable(fresh_import, monkeypatch):
    manager_module = load_manager(fresh_import)
    monkeypatch.setattr(manager_module.AudioSessionManager, "_check_pycaw", lambda self: False)
    manager = manager_module.AudioSessionManager()

    assert manager.mute_session("obs.exe") is False


def test_mute_session_updates_matching_process(fresh_import, monkeypatch):
    session = SessionStub("obs.exe", 1)
    install_pycaw(monkeypatch, [session])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.mute_session("obs.exe", False) is True
    assert session.volume_stub.mute_calls == [False]


def test_mute_session_returns_false_when_not_found(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [SessionStub("game.exe", 1)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.mute_session("obs.exe") is False


@pytest.mark.parametrize(("value", "expected"), [(-1.0, 0.0), (0.4, 0.4), (2.0, 1.0)])
def test_set_session_volume_clamps_values(fresh_import, monkeypatch, value, expected):
    session = SessionStub("obs.exe", 1)
    install_pycaw(monkeypatch, [session])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.set_session_volume("obs.exe", value) is True
    assert session.volume_stub.volume_calls[-1] == expected


def test_set_session_volume_returns_false_when_missing(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [SessionStub("game.exe", 1)])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.set_session_volume("obs.exe", 0.5) is False


def test_get_loopback_devices_returns_system_audio(fresh_import, monkeypatch):
    install_pycaw(monkeypatch, [])
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.get_loopback_devices() == [{"name": "System Audio (Loopback)", "id": "loopback"}]


def test_get_loopback_devices_returns_empty_on_error(fresh_import, monkeypatch):
    pycaw_module = types.ModuleType("pycaw.pycaw")
    pycaw_module.AudioUtilities = types.SimpleNamespace(
        GetSpeakers=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setitem(sys.modules, "pycaw", types.ModuleType("pycaw"))
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", pycaw_module)
    manager_module = load_manager(fresh_import)
    manager = manager_module.AudioSessionManager()

    assert manager.get_loopback_devices() == []


def test_install_dependencies_skips_when_available(fresh_import, monkeypatch):
    monkeypatch.setitem(sys.modules, "pycaw", types.ModuleType("pycaw"))
    manager_module = load_manager(fresh_import)

    manager_module.AudioSessionManager.install_dependencies()


def test_install_dependencies_runs_pip_when_missing(fresh_import, monkeypatch):
    import subprocess

    monkeypatch.setitem(sys.modules, "pycaw", None)
    manager_module = load_manager(fresh_import)
    calls = []
    monkeypatch.setattr(subprocess, "check_call", lambda args: calls.append(args))

    manager_module.AudioSessionManager.install_dependencies()

    assert calls
