"""
Screen Recorder v1.3.0 for NeoRecorder.
- Progress monitoring integration
- Segment-based pause support
- Thread-safe operations
- Explicit recorder state transitions
"""

from __future__ import annotations

import datetime
import os
import threading
from typing import Callable, Dict, List, Optional

from config import DEFAULT_FPS, DEFAULT_FORMAT, DEFAULT_QUALITY
from core.runtime.models import OutputMode, OutputSession, OutputSessionSnapshot, RecorderState, StreamSettings
from utils.ffmpeg_handler import FFmpegHandler, RecordingProgress
from utils.logger import log_recording_start, log_recording_stop


class ScreenRecorder:
    def __init__(self):
        self.handler = FFmpegHandler()
        self.state = RecorderState.IDLE
        self.is_recording = False
        self.output_dir = os.path.join(os.path.expanduser("~"), "Videos", "NeoRecorder")
        self.current_output_path: Optional[str] = None
        self.fps = DEFAULT_FPS
        self.quality = DEFAULT_QUALITY
        self._on_recording_complete: Optional[Callable[[Dict], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_warning: Optional[Callable[[str], None]] = None
        self._on_progress: Optional[Callable[[RecordingProgress], None]] = None
        self._lock = threading.RLock()
        self._last_request = None
        self._last_stream_settings: Optional[StreamSettings] = None
        self._last_record_to_file = True
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
        except Exception as exc:
            print(f"Error creating output dir: {exc}")

    def set_callbacks(self, on_complete=None, on_error=None, on_progress=None, on_warning=None):
        self._on_recording_complete = on_complete
        self._on_error = on_error
        self._on_progress = on_progress
        self._on_warning = on_warning
        self.handler.set_callbacks(
            on_stopped=self._handle_recording_stopped,
            on_error=self._handle_error,
            on_progress=self._handle_progress,
            on_warning=self._handle_warning,
        )

    def _handle_recording_stopped(self, result: Dict):
        self._set_state(RecorderState.IDLE)
        if self._on_recording_complete:
            self._on_recording_complete(result)

    def _handle_error(self, error: str):
        self._set_state(RecorderState.FAILED)
        print(f"Recording error: {error}")
        if self._on_error:
            self._on_error(error)

    def _handle_warning(self, message: str):
        print(f"Recording warning: {message}")
        if self._on_warning:
            self._on_warning(message)

    def _handle_progress(self, progress: RecordingProgress):
        if self._on_progress:
            self._on_progress(progress)

    def _set_state(self, state: RecorderState):
        self.state = state
        self.is_recording = state in {
            RecorderState.STARTING,
            RecorderState.RECORDING,
            RecorderState.PAUSING,
            RecorderState.PAUSED,
            RecorderState.STOPPING,
        }

    def set_fps(self, fps: int):
        with self._lock:
            if fps in [30, 60, 120, 144, 240]:
                self.fps = fps
            else:
                print(f"Invalid FPS value: {fps}")

    def set_quality(self, quality_preset: str):
        with self._lock:
            if quality_preset in ["ultrafast", "balanced", "quality", "lossless"]:
                self.quality = quality_preset
            else:
                print(f"Invalid quality preset: {quality_preset}")

    def start(
        self,
        mode="fullscreen",
        rect=None,
        mic=None,
        system=False,
        scene_plan=None,
        stream_settings=None,
        record_to_file: bool = True,
    ) -> Optional[str]:
        with self._lock:
            if self.is_recording or self.state not in {RecorderState.IDLE, RecorderState.FAILED}:
                print("Warning: Already recording")
                return None
            self._ensure_output_dir()
            self._set_state(RecorderState.STARTING)
            output_path = self._build_output_path() if record_to_file else None
            started = self._start_handler(
                output_path=output_path,
                rect=rect,
                mic=mic,
                system=system,
                scene_plan=scene_plan,
                stream_settings=stream_settings,
                record_to_file=record_to_file,
            )
            if not started:
                self.current_output_path = None
                self._set_state(RecorderState.FAILED)
                return None
            self.current_output_path = output_path
            self._set_state(RecorderState.RECORDING)
            self._log_start(output_path)
            return output_path

    def _build_output_path(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Record_{timestamp}.{DEFAULT_FORMAT}"
        return os.path.join(self.output_dir, filename)

    def _start_handler(
        self,
        output_path,
        rect,
        mic,
        system,
        scene_plan,
        stream_settings,
        record_to_file,
    ) -> bool:
        if stream_settings and stream_settings.is_configured() and not record_to_file:
            return self.handler.start_streaming(
                stream_settings=stream_settings,
                rect=rect,
                mic=mic,
                system=system,
                scene_plan=scene_plan,
                framerate=self.fps,
                quality_preset=self.quality,
            )
        return self.handler.start_recording(
            output_path,
            rect=rect,
            mic=mic,
            system=system,
            scene_plan=scene_plan,
            framerate=self.fps,
            quality_preset=self.quality,
            stream_settings=stream_settings,
        )

    def _log_start(self, output_path: Optional[str]):
        log_recording_start(
            output_path or "stream-only",
            self.fps,
            self.quality,
            getattr(self.handler, "current_encoder", None) or self.handler.get_best_encoder(),
        )

    def start_request(self, request, stream_settings=None, record_to_file: bool = True) -> Optional[str]:
        self._last_request = request
        self._last_stream_settings = stream_settings
        self._last_record_to_file = record_to_file
        if stream_settings is None and record_to_file:
            return self.start(
                mode=request.mode,
                rect=request.rect,
                mic=request.mic,
                system=request.system,
                scene_plan=request.plan,
            )
        return self.start(
            mode=request.mode,
            rect=request.rect,
            mic=request.mic,
            system=request.system,
            scene_plan=request.plan,
            stream_settings=stream_settings,
            record_to_file=record_to_file,
        )

    def stop(self) -> Optional[Dict]:
        with self._lock:
            if not self.is_recording and self.state not in {RecorderState.RECORDING, RecorderState.PAUSED, RecorderState.FAILED}:
                return None
            self._set_state(RecorderState.STOPPING)
            result = self.handler.stop_recording()
            self._set_state(RecorderState.IDLE)
            if not result:
                return None
            enriched = self._enrich_result(result)
            log_recording_stop(enriched.get("output_path", ""), enriched.get("duration", 0), enriched.get("segments_count", 1))
            return enriched

    def enable_stream(self, stream_settings: StreamSettings) -> bool:
        with self._lock:
            if self.state not in {RecorderState.RECORDING, RecorderState.PAUSED}:
                return False
            return self.handler.start_stream_output(stream_settings)

    def disable_stream(self) -> bool:
        with self._lock:
            return self.handler.stop_stream_output()

    def is_streaming(self) -> bool:
        return self.handler.is_streaming()

    def get_output_session(self) -> OutputSession:
        return self.handler.get_output_session()

    def snapshot_output_session(self) -> OutputSessionSnapshot:
        session = self.get_output_session()
        return OutputSessionSnapshot(
            request=self._last_request,
            mode=session.mode,
            stream_settings=self._last_stream_settings,
            record_to_file=session.mode != OutputMode.STREAM,
            software_fallback_active=session.software_fallback_active,
        )

    def restore_output_session(
        self,
        snapshot: OutputSessionSnapshot,
        prefer_software: bool = False,
    ) -> Optional[str]:
        if not snapshot.is_recoverable():
            return None
        with self._lock:
            if self.is_recording:
                self.stop()
            self.handler.set_force_safe_mode(prefer_software)
            if snapshot.mode == OutputMode.STREAM:
                return self.start_request(snapshot.request, snapshot.stream_settings, record_to_file=False)
            output = self.start_request(snapshot.request, None, record_to_file=True)
            if output is None:
                return None
            if snapshot.mode == OutputMode.RECORD_AND_STREAM and snapshot.stream_settings:
                if not self.enable_stream(snapshot.stream_settings):
                    return output
            return output

    def _enrich_result(self, result: Dict) -> Dict:
        result["path"] = self.output_dir
        result["full_path"] = result.get("output_path")
        result["duration_formatted"] = self._format_duration(result.get("duration", 0))
        progress = result.get("last_progress")
        if progress:
            result["total_frames"] = progress.frame
            result["avg_fps"] = progress.fps
            result["final_bitrate"] = progress.bitrate
        return result

    def pause(self) -> bool:
        with self._lock:
            if not self.is_recording and self.state != RecorderState.RECORDING:
                return False
            self._set_state(RecorderState.PAUSING)
            paused = self.handler.pause()
            self._set_state(RecorderState.PAUSED if paused else RecorderState.RECORDING)
            return paused

    def resume(self) -> bool:
        with self._lock:
            if not (self.state == RecorderState.PAUSED or self.handler.is_paused()):
                return False
            resumed = self.handler.resume()
            self._set_state(RecorderState.RECORDING if resumed else RecorderState.FAILED)
            return resumed

    def toggle_pause(self) -> bool:
        if self.state == RecorderState.PAUSED:
            return not self.resume()
        return self.pause()

    def is_paused(self) -> bool:
        return self.state == RecorderState.PAUSED or self.handler.is_paused()

    def get_elapsed_time(self) -> float:
        if not self.is_recording and self.state not in {RecorderState.RECORDING, RecorderState.PAUSED}:
            return 0
        return self.handler.get_elapsed_time()

    def get_elapsed_formatted(self) -> str:
        return self._format_duration(self.get_elapsed_time())

    def get_progress(self) -> RecordingProgress:
        return self.handler.get_progress()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = int(max(0, seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def get_output_dir(self) -> str:
        return self.output_dir

    def set_output_dir(self, new_dir: str) -> bool:
        with self._lock:
            try:
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir, exist_ok=True)
                if not os.path.isdir(new_dir):
                    print(f"Not a directory: {new_dir}")
                    return False
                self.output_dir = new_dir
                return True
            except Exception as exc:
                print(f"Error setting output dir: {exc}")
                return False

    def get_available_encoders(self) -> List[str]:
        return self.handler.get_available_encoders()

    def get_best_encoder(self) -> str:
        return self.handler.get_best_encoder()

    def get_current_settings(self) -> Dict:
        return {
            "fps": self.fps,
            "quality": self.quality,
            "encoder": self.get_best_encoder(),
            "output_dir": self.output_dir,
            "state": self.state.value,
        }
