import types


class StreamStub:
    def __init__(self, payloads=None, error=None):
        self.payloads = payloads or [b"\x00\x80" * 4]
        self.error = error
        self.stopped = False
        self.closed = False

    def read(self, _chunk, exception_on_overflow=False):
        if self.payloads:
            return self.payloads.pop(0)
        if self.error:
            raise self.error
        return b""

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class PyAudioStub:
    def __init__(self, devices=None, stream=None, host_error=None):
        self.devices = devices or []
        self.stream = stream or StreamStub()
        self.host_error = host_error
        self.terminated = False

    def get_host_api_info_by_index(self, _index):
        if self.host_error:
            raise self.host_error
        return {"deviceCount": len(self.devices)}

    def get_device_info_by_host_api_device_index(self, _api, index):
        device = self.devices[index]
        if isinstance(device, Exception):
            raise device
        return device

    def open(self, **_kwargs):
        return self.stream

    def terminate(self):
        self.terminated = True


def load_audio_manager(fresh_import):
    return fresh_import("core.audio_manager")


def test_init_sets_initialized_flag_on_success(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub())

    manager = audio_manager.AudioManager()

    assert manager._initialized is True
    assert manager.pa is not None


def test_init_handles_pyaudio_failure(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(
        audio_manager.pyaudio,
        "PyAudio",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    manager = audio_manager.AudioManager()

    assert manager._initialized is False
    assert manager.pa is None


def test_get_input_devices_returns_empty_when_uninitialized(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub())
    manager = audio_manager.AudioManager()
    manager._initialized = False

    assert manager.get_input_devices() == []


def test_get_input_devices_filters_input_channels(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    pa = PyAudioStub(
        devices=[
            {"maxInputChannels": 2, "name": "Mic", "index": 0},
            {"maxInputChannels": 0, "name": "Speaker", "index": 1},
        ]
    )
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: pa)

    manager = audio_manager.AudioManager()

    assert manager.get_input_devices() == [{"index": 0, "name": "Mic"}]


def test_get_input_devices_ignores_broken_device(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    pa = PyAudioStub(devices=[RuntimeError("broken"), {"maxInputChannels": 1, "name": "Mic"}])
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: pa)

    manager = audio_manager.AudioManager()

    assert manager.get_input_devices() == [{"index": 1, "name": "Mic"}]


def test_get_input_devices_handles_host_api_error(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(
        audio_manager.pyaudio,
        "PyAudio",
        lambda: PyAudioStub(host_error=RuntimeError("host error")),
    )

    manager = audio_manager.AudioManager()

    assert manager.get_input_devices() == []


def test_fix_device_name_encoding_returns_fallback_for_empty(fresh_import):
    audio_manager = load_audio_manager(fresh_import)

    assert audio_manager.AudioManager._fix_device_name_encoding("") == "Unknown Device"


def test_start_monitoring_returns_when_uninitialized(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub())
    manager = audio_manager.AudioManager()
    manager._initialized = False

    manager.start_monitoring(1)

    assert manager.is_monitoring is False


def test_start_monitoring_starts_thread(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub())
    manager = audio_manager.AudioManager()
    calls = []

    def fake_thread(target, args, daemon, name):
        calls.append((target, args, daemon, name))
        return types.SimpleNamespace(start=lambda: None)

    monkeypatch.setattr(audio_manager.threading, "Thread", fake_thread)

    manager.start_monitoring(5)

    assert manager.is_monitoring is True
    assert calls[0][1] == (5,)


def test_stop_monitoring_resets_level(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub())
    manager = audio_manager.AudioManager()
    manager.is_monitoring = True
    manager.vu_level = 0.7

    manager.stop_monitoring()

    assert manager.is_monitoring is False
    assert manager.get_vu_level() == 0
    assert manager.get_audio_levels() == (0, 0)


def test_monitor_thread_updates_vu_level(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    stream = StreamStub(payloads=[b"\xff\x7f" * 8], error=RuntimeError("stop"))
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: PyAudioStub(stream=stream))
    manager = audio_manager.AudioManager()
    manager.is_monitoring = True

    manager._monitor_thread(0)

    assert 0 < manager.get_vu_level() <= 1.0
    peak, rms = manager.get_audio_levels()
    assert peak >= rms >= 0
    assert stream.stopped is True
    assert stream.closed is True


def test_monitor_thread_handles_open_error(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)

    class BrokenPyAudio(PyAudioStub):
        def open(self, **_kwargs):
            raise RuntimeError("open failed")

    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: BrokenPyAudio())
    manager = audio_manager.AudioManager()
    manager.is_monitoring = True

    manager._monitor_thread(0)

    assert manager.is_monitoring is False


def test_terminate_stops_stream_and_releases_pyaudio(fresh_import, monkeypatch):
    audio_manager = load_audio_manager(fresh_import)
    pa = PyAudioStub()
    monkeypatch.setattr(audio_manager.pyaudio, "PyAudio", lambda: pa)
    manager = audio_manager.AudioManager()
    manager.is_monitoring = True

    manager.terminate()

    assert pa.terminated is True
    assert manager.pa is None
    assert manager._initialized is False
