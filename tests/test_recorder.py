import types

import pytest


class HandlerStub:
    def __init__(self):
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState"])
        self.callbacks = {}
        self.start_calls = []
        self.stop_result = None
        self.pause_result = True
        self.resume_result = True
        self.toggle_result = True
        self.paused = False
        self.elapsed = 12.3
        self.progress = types.SimpleNamespace(frame=120, fps=60.0, bitrate="3000kbits/s")
        self.stream_started = False
        self.output_session = runtime_models.OutputSession(stream_state=runtime_models.StreamState.DISABLED)

    def set_callbacks(self, **kwargs):
        self.callbacks = kwargs

    def start_recording(self, *args, **kwargs):
        self.start_calls.append((args, kwargs))
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState"])
        self.output_session = runtime_models.OutputSession(
            mode=runtime_models.OutputMode.RECORD,
            record_path=args[0] if args else None,
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.DISABLED,
        )
        return True

    def start_streaming(self, *args, **kwargs):
        self.start_calls.append((args, kwargs))
        runtime_models = __import__("core.runtime.models", fromlist=["OutputSession", "OutputMode", "StreamState"])
        settings = kwargs.get("stream_settings")
        self.output_session = runtime_models.OutputSession(
            mode=runtime_models.OutputMode.STREAM,
            record_path=None,
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.LIVE,
            stream_url=settings.output_url() if settings else None,
        )
        self.stream_started = True
        return True

    def stop_recording(self):
        return self.stop_result

    def pause(self):
        return self.pause_result

    def resume(self):
        return self.resume_result

    def toggle_pause(self):
        return self.toggle_result

    def is_paused(self):
        return self.paused

    def get_elapsed_time(self):
        return self.elapsed

    def get_progress(self):
        return self.progress

    def get_available_encoders(self):
        return ["libx264"]

    def get_best_encoder(self):
        return "libx264"

    def start_stream_output(self, stream_settings):
        self.stream_started = True
        runtime_models = __import__("core.runtime.models", fromlist=["OutputMode", "StreamState"])
        mode = self.output_session.mode if self.output_session.mode != runtime_models.OutputMode.IDLE else runtime_models.OutputMode.RECORD_AND_STREAM
        self.output_session = self.output_session.__class__(
            mode=mode,
            record_path=self.output_session.record_path,
            bridge_url="udp://127.0.0.1:23000",
            stream_state=runtime_models.StreamState.LIVE,
            stream_url=stream_settings.output_url(),
            reconnect_attempts=0,
        )
        return True

    def stop_stream_output(self):
        self.stream_started = False
        return True

    def is_streaming(self):
        return self.stream_started

    def get_output_session(self):
        return self.output_session

    def set_force_safe_mode(self, enabled):
        self.force_safe_mode = enabled


def load_recorder(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return fresh_import("core.recorder")


def test_set_callbacks_registers_handler_callbacks(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()

    recorder.set_callbacks(on_complete="done", on_error="error", on_progress="progress")

    assert recorder.handler.callbacks["on_stopped"] == recorder._handle_recording_stopped
    assert recorder.handler.callbacks["on_error"] == recorder._handle_error


@pytest.mark.parametrize("fps", [30, 60, 120, 144, 240])
def test_set_fps_accepts_supported_values(fresh_import, monkeypatch, tmp_path, fps):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()

    recorder.set_fps(fps)

    assert recorder.fps == fps


def test_set_fps_rejects_invalid_value(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()

    recorder.set_fps(999)

    assert recorder.fps == recorder_module.DEFAULT_FPS


@pytest.mark.parametrize("quality", ["ultrafast", "balanced", "quality", "lossless"])
def test_set_quality_accepts_supported_values(fresh_import, monkeypatch, tmp_path, quality):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()

    recorder.set_quality(quality)

    assert recorder.quality == quality


def test_set_quality_rejects_invalid_value(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()

    recorder.set_quality("bad")

    assert recorder.quality == recorder_module.DEFAULT_QUALITY


def test_start_returns_none_when_already_recording(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.is_recording = True

    assert recorder.start() is None


def test_start_returns_output_path_on_success(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()

    result = recorder.start(rect=(1, 2, 3, 4), mic="Mic", system=True)

    assert result is not None
    assert recorder.is_recording is True
    assert recorder.handler.start_calls[0][1]["mic"] == "Mic"


def test_start_clears_current_output_on_failure(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.handler.start_recording = lambda *args, **kwargs: False

    assert recorder.start() is None
    assert recorder.current_output_path is None


def test_start_request_delegates_to_start(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    calls = []
    monkeypatch.setattr(
        recorder,
        "start",
        lambda **kwargs: calls.append(kwargs) or "out.mp4",
    )
    request = types.SimpleNamespace(mode="region", rect=(1, 2, 3, 4), mic="Mic", system=True, plan="plan")

    result = recorder.start_request(request)

    assert result == "out.mp4"
    assert calls == [{"mode": "region", "rect": (1, 2, 3, 4), "mic": "Mic", "system": True, "scene_plan": "plan"}]


def test_stop_returns_none_when_not_recording(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)

    assert recorder_module.ScreenRecorder().stop() is None


def test_stop_enriches_result(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.is_recording = True
    recorder.handler.stop_result = {
        "output_path": str(tmp_path / "out.mp4"),
        "duration": 65,
        "segments_count": 2,
        "last_progress": recorder.handler.progress,
    }

    result = recorder.stop()

    assert result["duration_formatted"] == "01:05"
    assert result["total_frames"] == 120
    assert result["avg_fps"] == 60.0
    assert recorder.is_recording is False


def test_pause_resume_and_toggle_delegate_to_handler(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.is_recording = True

    assert recorder.pause() is True
    assert recorder.resume() is True
    assert recorder.toggle_pause() is True


def test_pause_returns_false_when_not_recording(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)

    assert recorder_module.ScreenRecorder().pause() is False


def test_get_elapsed_helpers_format_duration(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.is_recording = True
    recorder.handler.elapsed = 3661

    assert recorder.get_elapsed_time() == 3661
    assert recorder.get_elapsed_formatted() == "01:01:01"


def test_set_output_dir_updates_directory(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    new_dir = tmp_path / "captures"

    assert recorder.set_output_dir(str(new_dir)) is True
    assert recorder.get_output_dir() == str(new_dir)


def test_set_output_dir_returns_false_on_error(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    monkeypatch.setattr(recorder_module.os, "makedirs", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("boom")))

    assert recorder.set_output_dir(str(tmp_path / "bad")) is False


def test_get_current_settings_returns_snapshot(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.set_fps(120)
    recorder.set_quality("quality")

    result = recorder.get_current_settings()

    assert result["fps"] == 120
    assert result["quality"] == "quality"
    assert result["encoder"] == "libx264"


def test_recorder_exposes_state_machine_transitions(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    runtime_models = fresh_import("core.runtime.models")
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()

    recorder.start()
    paused = recorder.pause()
    resumed = recorder.resume()
    recorder.stop()

    assert paused is True
    assert resumed is True
    assert recorder.state == runtime_models.RecorderState.IDLE


def test_start_request_stream_only_uses_extended_signature(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    runtime_models = fresh_import("core.runtime.models")
    recorder = recorder_module.ScreenRecorder()
    calls = []
    monkeypatch.setattr(recorder, "start", lambda **kwargs: calls.append(kwargs) or None)
    request = types.SimpleNamespace(mode="region", rect=(1, 2, 3, 4), mic="Mic", system=True, plan="plan")
    stream = runtime_models.StreamSettings(enabled=True, server_url="rtmp://live", stream_key="abc")

    recorder.start_request(request, stream_settings=stream, record_to_file=False)

    assert calls[0]["record_to_file"] is False
    assert calls[0]["stream_settings"] == stream


def test_recorder_enable_and_disable_stream_delegate_to_handler(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    runtime_models = fresh_import("core.runtime.models")
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    recorder.is_recording = True
    recorder.state = runtime_models.RecorderState.RECORDING
    stream = runtime_models.StreamSettings(enabled=True, server_url="rtmp://live", stream_key="abc")

    assert recorder.enable_stream(stream) is True
    assert recorder.is_streaming() is True
    assert recorder.disable_stream() is True


def test_recorder_snapshot_and_restore_output_session(fresh_import, monkeypatch, tmp_path):
    recorder_module = load_recorder(fresh_import, monkeypatch, tmp_path)
    runtime_models = fresh_import("core.runtime.models")
    recorder = recorder_module.ScreenRecorder()
    recorder.handler = HandlerStub()
    request = types.SimpleNamespace(mode="region", rect=(1, 2, 3, 4), mic="Mic", system=True, plan="plan")
    stream = runtime_models.StreamSettings(enabled=True, server_url="rtmp://live", stream_key="abc")
    recorder.start_request(request, stream_settings=stream, record_to_file=False)
    snapshot = recorder.snapshot_output_session()
    calls = []
    monkeypatch.setattr(recorder, "start_request", lambda *args, **kwargs: calls.append((args, kwargs)) or "restored.mp4")

    result = recorder.restore_output_session(snapshot, prefer_software=True)

    assert result == "restored.mp4"
    assert calls[0][1]["record_to_file"] is False
