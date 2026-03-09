import logging
import sys

import pytest


def load_logger(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return fresh_import("utils.logger")


def test_get_logger_creates_file_and_console_handlers(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)

    logger = logger_module.get_logger()

    assert len(logger.handlers) == 2
    log_dir = tmp_path / "Videos" / "NeoRecorder" / "logs"
    assert log_dir.exists()


def test_get_logger_skips_console_when_frozen(fresh_import, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)

    logger = logger_module.get_logger()

    assert len(logger.handlers) == 1


def test_get_logger_returns_cached_instance(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)

    assert logger_module.get_logger() is logger_module.get_logger()


def test_get_logger_caches_by_name(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)

    default_logger = logger_module.get_logger()
    other_logger = logger_module.get_logger("Other")

    assert default_logger is not other_logger
    assert other_logger.name == "Other"


def test_log_recording_start_writes_messages(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_recording_start("video.mp4", 60, "balanced", "libx264")

    assert any("Recording started: video.mp4" in record.getMessage() for record in handler.records)


def test_log_recording_stop_writes_duration(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_recording_stop("video.mp4", 125, 2)

    messages = [record.getMessage() for record in handler.records]
    assert any("Recording stopped: video.mp4" in message for message in messages)
    assert any("Duration: 2m 5s, Segments: 2" in message for message in messages)


def test_log_error_uses_error_level(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_error("capture", RuntimeError("boom"))

    assert any(record.levelno == logging.ERROR for record in handler.records)


def test_log_warning_uses_warning_level(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_warning("warn")

    assert any(record.levelno == logging.WARNING for record in handler.records)


def test_log_debug_uses_debug_level(fresh_import, monkeypatch, tmp_path):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_debug("debug")

    assert any(record.levelno == logging.DEBUG for record in handler.records)


@pytest.mark.parametrize(
    ("line", "level"),
    [
        ("error while encoding", logging.WARNING),
        ("warning: slow capture", logging.WARNING),
        ("frame=10 fps=60", logging.DEBUG),
    ],
)
def test_log_ffmpeg_output_routes_levels(
    fresh_import,
    monkeypatch,
    tmp_path,
    line,
    level,
):
    logger_module = load_logger(fresh_import, monkeypatch, tmp_path)
    logger = logger_module.get_logger()
    handler = MemoryHandler()
    logger.addHandler(handler)

    logger_module.log_ffmpeg_output(line)

    assert any(record.levelno == level for record in handler.records)


class MemoryHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)
