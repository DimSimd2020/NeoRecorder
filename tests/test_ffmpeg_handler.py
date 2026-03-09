import io
from pathlib import Path
import types

import pytest


class CompletedStub:
    def __init__(self, returncode=0, stdout="", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class StdinStub:
    def __init__(self):
        self.payload = []

    def write(self, value):
        self.payload.append(value)

    def flush(self):
        return None


class StderrStub:
    def __init__(self, lines=None, tail=b""):
        self.lines = list(lines or [])
        self.tail = tail

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        return b""

    def read(self):
        return self.tail


class PopenStub:
    def __init__(self, returncode=None, lines=None):
        self.returncode = returncode
        self.stdin = StdinStub()
        self.stdout = io.BytesIO()
        self.stderr = StderrStub(lines=lines)
        self.terminated = False
        self.killed = False
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -1

    def kill(self):
        self.killed = True
        self.returncode = -9


def load_handler(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return fresh_import("utils.ffmpeg_handler")


def test_get_available_encoders_returns_cached_value(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._available_encoders = ["h264_nvenc"]

    assert handler.get_available_encoders() == ["h264_nvenc"]


def test_get_available_encoders_detects_supported_hardware(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(
            stdout="h264_nvenc\nh264_qsv\nh264_amf\n"
        ),
    )
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(
        handler,
        "_test_encoder",
        lambda encoder: encoder in {"h264_nvenc", "h264_amf"},
    )

    assert handler.get_available_encoders() == ["h264_nvenc", "h264_amf"]


def test_get_available_encoders_returns_empty_on_failure(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    handler = handler_module.FFmpegHandler()

    assert handler.get_available_encoders() == []


def test_test_encoder_returns_true_on_zero_exit_code(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(returncode=0),
    )

    assert handler_module.FFmpegHandler()._test_encoder("h264_nvenc") is True


def test_test_encoder_returns_false_on_exception(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert handler_module.FFmpegHandler()._test_encoder("h264_nvenc") is False


def test_get_best_encoder_returns_cpu_when_hardware_disabled(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(handler_module, "USE_HARDWARE_ENCODER", False)

    assert handler_module.FFmpegHandler().get_best_encoder() == "libx264"


@pytest.mark.parametrize(
    ("encoders", "expected"),
    [
        (["h264_qsv"], "h264_qsv"),
        (["h264_amf"], "h264_amf"),
        ([], "libx264"),
    ],
)
def test_get_best_encoder_uses_priority(fresh_import, monkeypatch, tmp_path, encoders, expected):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler, "get_available_encoders", lambda: encoders)

    assert handler.get_best_encoder() == expected


def test_encoder_candidates_filter_incompatible_hardware(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler, "get_available_encoders", lambda: ["h264_qsv", "h264_amf"])

    assert handler._encoder_candidates(capture_width=5000, framerate=60) == ["libx264"]


def test_start_recording_returns_false_when_already_recording(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._is_recording = True

    assert handler.start_recording("out.mp4") is False


def test_start_recording_initializes_state(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path / "segments"))
    monkeypatch.setattr(handler, "_start_segment", lambda: True)

    result = handler.start_recording("out.mp4", rect=(1, 2, 3, 4), mic="Mic", system=True)

    assert result is True
    assert handler._recording_params["mic"] == "Mic"
    assert handler._final_output == "out.mp4"


def test_start_recording_cleans_failed_start(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path / "segments"))
    monkeypatch.setattr(handler, "_start_segment", lambda: False)
    cleaned = []
    monkeypatch.setattr(handler, "_cleanup_temp", lambda: cleaned.append(True))

    result = handler.start_recording("out.mp4")

    assert result is False
    assert cleaned == [True]
    assert handler._recording_params is None


def test_start_segment_requires_temp_dir_and_params(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()

    assert handler._start_segment() is False


def test_start_segment_appends_segment_on_success(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._temp_dir = str(tmp_path)
    handler._recording_params = {
        "rect": None,
        "mic": None,
        "system": False,
        "framerate": 60,
        "quality_preset": "balanced",
    }
    started = []
    handler.set_callbacks(on_started=lambda: started.append(True))
    monkeypatch.setattr(handler, "_try_ffmpeg", lambda *args: True)

    result = handler._start_segment()

    assert result is True
    assert len(handler._segments) == 1
    assert started == [True]


def test_start_segment_does_not_append_on_failure(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._temp_dir = str(tmp_path)
    handler._recording_params = {
        "rect": None,
        "mic": None,
        "system": False,
        "framerate": 60,
        "quality_preset": "balanced",
    }
    monkeypatch.setattr(handler, "_try_ffmpeg", lambda *args: False)

    assert handler._start_segment() is False
    assert handler._segments == []
    assert handler.current_output is None


def test_get_gdigrab_resolution_parses_stderr(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(stderr="Video: bmp, bgra, 5120x1440,"),
    )

    assert handler_module.FFmpegHandler()._get_gdigrab_resolution() == (5120, 1440)


def test_get_gdigrab_resolution_returns_zero_on_error(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert handler_module.FFmpegHandler()._get_gdigrab_resolution() == (0, 0)


def test_pause_returns_false_when_not_recording(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)

    assert handler_module.FFmpegHandler().pause() is False


def test_pause_stops_process_and_marks_paused(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._is_recording = True
    handler.process = PopenStub()

    assert handler.pause() is True
    assert handler.process is None
    assert handler.is_paused() is True


def test_resume_returns_false_when_not_paused(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)

    assert handler_module.FFmpegHandler().resume() is False


def test_resume_updates_pause_duration_on_success(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._is_recording = True
    handler._is_paused = True
    handler._pause_start = 10.0
    monkeypatch.setattr(handler_module.time, "time", lambda: 15.0)
    monkeypatch.setattr(handler, "_start_segment", lambda: True)

    assert handler.resume() is True
    assert handler._total_pause_duration == 5.0
    assert handler._pause_start is None


def test_resume_restores_paused_state_on_failure(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._is_recording = True
    handler._is_paused = True
    handler._pause_start = 10.0
    errors = []
    handler.set_callbacks(on_error=errors.append)
    monkeypatch.setattr(handler, "_start_segment", lambda: False)

    assert handler.resume() is False
    assert handler.is_paused() is True
    assert errors == ["Failed to resume recording"]


def test_toggle_pause_reflects_pause_state(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler, "pause", lambda: True)

    assert handler.toggle_pause() is True


def test_toggle_pause_keeps_paused_when_resume_fails(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler._is_paused = True
    monkeypatch.setattr(handler, "resume", lambda: False)

    assert handler.toggle_pause() is True


def test_toggle_pause_returns_false_when_pause_fails(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler, "pause", lambda: False)

    assert handler.toggle_pause() is False


def test_stop_recording_returns_result_and_resets_state(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler.start_timestamp = 10.0
    handler._is_recording = True
    handler.process = PopenStub()
    handler._segments = ["a.mp4"]
    handler._last_progress = handler_module.RecordingProgress(frame=10, fps=60)
    monkeypatch.setattr(handler_module.time, "time", lambda: 20.0)
    monkeypatch.setattr(handler, "_merge_segments", lambda: "final.mp4")
    monkeypatch.setattr(handler, "_cleanup_temp", lambda: None)

    result = handler.stop_recording()

    assert result["output_path"] == "final.mp4"
    assert result["duration"] == 10.0
    assert handler._is_recording is False
    assert handler._recording_params is None


def test_merge_segments_returns_none_when_empty(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)

    assert handler_module.FFmpegHandler()._merge_segments() is None


def test_merge_segments_moves_single_file(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    source = tmp_path / "segment_0000.mp4"
    source.write_text("data", encoding="utf-8")
    handler._segments = [str(source)]
    handler._final_output = str(tmp_path / "final.mp4")

    result = handler._merge_segments()

    assert result == str(tmp_path / "final.mp4")
    assert Path(result).exists()


def test_merge_segments_uses_concat_for_multiple_files(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_text("1", encoding="utf-8")
    second.write_text("2", encoding="utf-8")
    handler._segments = [str(first), str(second)]
    handler._temp_dir = str(tmp_path)
    handler._final_output = str(tmp_path / "final.mp4")
    Path(handler._final_output).write_text("merged", encoding="utf-8")
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(returncode=0),
    )

    result = handler._merge_segments()

    assert result == handler._final_output


def test_merge_segments_falls_back_to_last_segment_on_concat_error(
    fresh_import,
    monkeypatch,
    tmp_path,
):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_text("1", encoding="utf-8")
    second.write_text("2", encoding="utf-8")
    handler._segments = [str(first), str(second)]
    handler._temp_dir = str(tmp_path)
    handler._final_output = str(tmp_path / "final.mp4")
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(returncode=1, stderr=b"failed"),
    )

    assert handler._merge_segments() == str(second)


def test_cleanup_temp_removes_directory(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    temp_dir = tmp_path / "segments"
    temp_dir.mkdir()
    handler._temp_dir = str(temp_dir)

    handler._cleanup_temp()

    assert temp_dir.exists() is False


def test_get_elapsed_time_returns_zero_without_start(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)

    assert handler_module.FFmpegHandler().get_elapsed_time() == 0


def test_get_elapsed_time_excludes_pause_duration(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    handler.start_timestamp = 10.0
    handler._total_pause_duration = 3.0
    monkeypatch.setattr(handler_module.time, "time", lambda: 20.0)

    assert handler.get_elapsed_time() == 7.0


def test_get_output_lines_respects_max_size(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    for value in ["a", "b", "c"]:
        handler._output_queue.put(value)

    assert handler.get_output_lines(max_lines=2) == ["a", "b"]


def test_get_dshow_audio_names_parses_unique_values(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    stderr = "\n".join(
        [
            "DirectShow audio devices",
            '[dshow @ 000]  "Microphone"',
            '[dshow @ 000]  "Microphone"',
            '[dshow @ 000]  "@device_cm_1"',
            "DirectShow video devices",
        ]
    )
    monkeypatch.setattr(
        handler_module.subprocess,
        "run",
        lambda *args, **kwargs: CompletedStub(stderr=stderr),
    )

    assert handler_module.FFmpegHandler().get_dshow_audio_names() == ["Microphone"]


def test_try_ffmpeg_evens_region_dimensions(
    fresh_import,
    monkeypatch,
    tmp_path,
):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    monkeypatch.setattr(handler, "_encoder_candidates", lambda *_args: ["libx264"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (5120, 1440))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or PopenStub(),
    )

    result = handler._try_ffmpeg(
        str(tmp_path / "out.mp4"),
        "gdigrab",
        (10, 20, 111, 79),
        None,
        False,
        None,
        120,
        "balanced",
    )

    assert result is True
    assert "100x58" in commands[0]


def test_try_ffmpeg_caps_fullscreen_high_resolution_fps(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    monkeypatch.setattr(handler, "_encoder_candidates", lambda *_args: ["libx264"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (5120, 1440))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or PopenStub(),
    )

    result = handler._try_ffmpeg(
        str(tmp_path / "out.mp4"),
        "gdigrab",
        None,
        None,
        False,
        None,
        120,
        "balanced",
    )

    assert result is True
    assert "60" in commands[0]


def test_try_ffmpeg_falls_back_from_amf_on_wide_resolution(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    monkeypatch.setattr(handler, "get_available_encoders", lambda: ["h264_amf"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (5000, 1440))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or PopenStub(),
    )

    handler._try_ffmpeg(str(tmp_path / "out.mp4"), "gdigrab", None, None, False, None, 60, "lossless")

    encoder_index = commands[0].index("-c:v") + 1
    assert commands[0][encoder_index] == "libx264"


def test_try_ffmpeg_returns_false_when_process_fails_to_start(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    monkeypatch.setattr(handler, "_encoder_candidates", lambda *_args: ["libx264"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (1920, 1080))
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert handler._try_ffmpeg(str(tmp_path / "out.mp4"), "gdigrab", None, None, False, None, 60, "balanced") is False


def test_try_ffmpeg_retries_with_cpu_after_hardware_failure(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    popen_results = [PopenStub(returncode=1), PopenStub()]

    monkeypatch.setattr(handler, "get_available_encoders", lambda: ["h264_qsv"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (1920, 1080))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or popen_results.pop(0),
    )

    assert handler._try_ffmpeg(str(tmp_path / "out.mp4"), "gdigrab", None, None, False, None, 60, "balanced") is True
    assert commands[0][commands[0].index("-c:v") + 1] == "h264_qsv"
    assert commands[1][commands[1].index("-c:v") + 1] == "libx264"
    assert handler.current_encoder == "libx264"


def test_try_ffmpeg_builds_filter_graph_for_overlays(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    plan = types.SimpleNamespace(
        primary_video=types.SimpleNamespace(rect=(0, 0, 1920, 1080)),
        overlays=(
            types.SimpleNamespace(rect=(100, 80, 420, 260), opacity=0.75),
            types.SimpleNamespace(rect=(640, 360, 960, 540), opacity=1.0),
        ),
        audio_channels=(),
    )
    monkeypatch.setattr(handler, "_encoder_candidates", lambda *_args: ["libx264"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (1920, 1080))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or PopenStub(),
    )

    result = handler._try_ffmpeg(
        str(tmp_path / "out.mp4"),
        "gdigrab",
        (0, 0, 1920, 1080),
        None,
        False,
        plan,
        60,
        "balanced",
    )

    assert result is True
    assert commands[0].count("-i") == 3
    filter_index = commands[0].index("-filter_complex") + 1
    assert "overlay=100:80" in commands[0][filter_index]
    assert "overlay=640:360" in commands[0][filter_index]


def test_try_ffmpeg_maps_audio_for_filter_graph(fresh_import, monkeypatch, tmp_path):
    handler_module = load_handler(fresh_import, monkeypatch, tmp_path)
    handler = handler_module.FFmpegHandler()
    commands = []
    plan = types.SimpleNamespace(
        primary_video=types.SimpleNamespace(rect=(0, 0, 1920, 1080)),
        overlays=(types.SimpleNamespace(rect=(10, 10, 210, 110), opacity=0.5),),
        audio_channels=(types.SimpleNamespace(target="USB Mic", muted=False, volume=0.35),),
    )
    monkeypatch.setattr(handler, "_encoder_candidates", lambda *_args: ["libx264"])
    monkeypatch.setattr(handler, "_get_gdigrab_resolution", lambda: (1920, 1080))
    monkeypatch.setattr(handler, "_start_output_monitor", lambda: None)
    monkeypatch.setattr(
        handler_module.subprocess,
        "Popen",
        lambda cmd, **kwargs: commands.append(cmd) or PopenStub(),
    )

    result = handler._try_ffmpeg(
        str(tmp_path / "out.mp4"),
        "gdigrab",
        (0, 0, 1920, 1080),
        "USB Mic",
        False,
        plan,
        60,
        "balanced",
    )

    assert result is True
    assert commands[0][commands[0].index("-map") + 1] == "[vout]"
    assert "2:a" in commands[0]
    assert "volume=0.35" in commands[0]
