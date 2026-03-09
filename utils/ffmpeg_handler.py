"""
FFmpeg Handler v1.3.0 for NeoRecorder.
- Segment-based pause (no NtSuspend risks)
- Real-time progress monitoring (fps, bitrate, frame count)
- Robust error handling and resource cleanup
"""

import subprocess
import os
import time
import threading
import queue
import re
import tempfile
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass
from config import FFMPEG_PATH, QUALITY_PRESETS, USE_HARDWARE_ENCODER
from utils.logger import get_logger, log_ffmpeg_output, log_error, log_debug

ENCODER_PRIORITY = ("h264_nvenc", "h264_qsv", "h264_amf")
ENCODER_LIMITS = {
    "h264_nvenc": {"max_width": None, "max_fps": 240},
    "h264_qsv": {"max_width": 4096, "max_fps": 144},
    "h264_amf": {"max_width": 3840, "max_fps": 120},
}


@dataclass
class RecordingProgress:
    """Progress data from FFmpeg output"""
    frame: int = 0
    fps: float = 0.0
    bitrate: str = "0kbits/s"
    size: str = "0kB"
    time: str = "00:00:00.00"
    speed: str = "0x"
    dropped: int = 0


@dataclass(frozen=True)
class EncoderDecision:
    """Resolved capture and encoder profile."""

    rect: Optional[tuple[int, int, int, int]]
    capture_width: int
    safe_framerate: int
    candidates: tuple[str, ...]


class FFmpegHandler:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.current_output: Optional[str] = None
        self.current_encoder: Optional[str] = None
        self.start_timestamp: Optional[float] = None
        self._available_encoders: Optional[list] = None
        
        # Segment-based pause
        self._segments: List[str] = []
        self._segment_index: int = 0
        self._is_paused: bool = False
        self._pause_start: Optional[float] = None
        self._total_pause_duration: float = 0.0
        self._recording_params: Optional[Dict] = None
        self._final_output: Optional[str] = None
        self._temp_dir: Optional[str] = None
        
        # Thread management
        self._worker_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_recording: bool = False
        
        # Callbacks
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_started: Optional[Callable[[], None]] = None
        self._on_stopped: Optional[Callable[[Dict], None]] = None
        self._on_progress: Optional[Callable[[RecordingProgress], None]] = None
        
        # Progress monitoring
        self._output_queue: queue.Queue = queue.Queue()
        self._last_progress: RecordingProgress = RecordingProgress()
        self._log_file = None

    def set_callbacks(self, on_started=None, on_stopped=None, on_error=None, on_progress=None):
        """Set callback functions for async events"""
        self._on_started = on_started
        self._on_stopped = on_stopped
        self._on_error = on_error
        self._on_progress = on_progress

    def get_progress(self) -> RecordingProgress:
        """Get current recording progress"""
        return self._last_progress

    def get_available_encoders(self) -> List[str]:
        """Detect available hardware encoders (cached) with actual test"""
        if self._available_encoders is not None:
            return self._available_encoders
        
        self._available_encoders = []
        
        # First get list of encoders from FFmpeg
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-encoders", "-hide_banner"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout
        except Exception as e:
            print(f"Error detecting encoders: {e}")
            return self._available_encoders
        
        # Test each hardware encoder with an actual encoding attempt
        hw_encoders = []
        if "h264_nvenc" in output:
            hw_encoders.append("h264_nvenc")
        if "h264_qsv" in output:
            hw_encoders.append("h264_qsv")
        if "h264_amf" in output:
            hw_encoders.append("h264_amf")
        
        for encoder in hw_encoders:
            if self._test_encoder(encoder):
                self._available_encoders.append(encoder)
                print(f"Hardware encoder available: {encoder}")
        
        return self._available_encoders
    
    def _test_encoder(self, encoder: str) -> bool:
        """Test if encoder actually works with real screen capture"""
        try:
            # Use gdigrab with small region for realistic test
            # nullsrc doesn't work with some GPU encoders (AMF)
            cmd = [
                FFMPEG_PATH, "-y",
                "-f", "gdigrab",
                "-framerate", "30",
                "-video_size", "640x480",
                "-t", "0.5",
                "-i", "desktop",
                "-c:v", encoder,
                "-f", "null", "-"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_best_encoder(self) -> str:
        """Get the best available encoder (prefer hardware)"""
        return self._encoder_candidates(capture_width=0, framerate=60)[0]

    def start_recording(self, output_path: str, rect=None, mic=None, system=False,
                       scene_plan=None,
                       framerate=60, quality_preset="balanced") -> bool:
        """
        Start recording. Uses segment-based approach for reliable pause.
        Returns True if started successfully.
        """
        if self._is_recording:
            log_debug("Warning: Already recording. Call stop first.")
            return False
        
        self._stop_event.clear()
        self._is_paused = False
        self._total_pause_duration = 0.0
        self._segments = []
        self._segment_index = 0
        self._final_output = output_path
        
        # Create temp directory for segments
        self._temp_dir = tempfile.mkdtemp(prefix="neorecorder_")
        
        # Store params for resume
        self._recording_params = {
            "rect": rect,
            "mic": mic,
            "system": system,
            "scene_plan": scene_plan,
            "framerate": framerate,
            "quality_preset": quality_preset
        }
        
        self.start_timestamp = time.time()
        
        # Start first segment
        success = self._start_segment()
        if success:
            return True

        self._cleanup_failed_start()
        return False

    def _cleanup_failed_start(self):
        """Reset state after a failed recording start"""
        self._close_log_file()
        self._cleanup_temp()
        self.current_output = None
        self.current_encoder = None
        self.start_timestamp = None
        self._recording_params = None
        self._final_output = None
        self._segments = []
        self._segment_index = 0
        self._is_recording = False

    def _start_segment(self) -> bool:
        """Start a new recording segment"""
        if not self._temp_dir or not self._recording_params:
            return False
        
        # Generate segment filename
        segment_path = os.path.join(
            self._temp_dir, 
            f"segment_{self._segment_index:04d}.mp4"
        )
        
        params = self._recording_params
        
        # Use gdigrab by default - it's more reliable
        # ddagrab requires complex filter setup and often fails
        success = self._try_ffmpeg(
            segment_path,
            "gdigrab",
            params["rect"],
            params["mic"],
            params["system"],
            params.get("scene_plan"),
            params["framerate"],
            params["quality_preset"]
        )
        
        if not success:
            self.current_output = None
            return False

        self.current_output = segment_path
        self._segments.append(segment_path)
        self._is_recording = True
        self._segment_index += 1
        if self._on_started:
            self._on_started()
        return True

    def _get_gdigrab_resolution(self) -> tuple[int, int]:
        """Get actual screen resolution via ffmpeg gdigrab probe"""
        try:
            cmd = [FFMPEG_PATH, "-f", "gdigrab", "-i", "desktop", "-t", "0.1", "-f", "null", "-"]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Look for: Video: bmp, bgra, 5120x1440, ...
            match = re.search(r'Video:.*,\s+(\d+)x(\d+)[,\s]', result.stderr)
            if match:
                return int(match.group(1)), int(match.group(2))
        except Exception as e:
            print(f"Error checking GDI resolution: {e}")
        return 0, 0
    
    def _try_ffmpeg(self, output_path: str, input_format: str, rect, mic,
                   system, scene_plan, framerate, quality_preset) -> bool:
        """Build and execute FFmpeg command with proper resource management"""
        quality = QUALITY_PRESETS.get(quality_preset, QUALITY_PRESETS["balanced"])
        decision = self._build_encoder_decision(input_format, rect, framerate)

        for encoder in decision.candidates:
            cmd = self._build_ffmpeg_command(
                output_path,
                input_format,
                decision.rect,
                mic,
                scene_plan,
                decision.safe_framerate,
                quality,
                encoder,
            )
            if self._launch_ffmpeg(
                cmd,
                output_path,
                encoder,
                framerate,
                decision.safe_framerate,
                quality_preset,
                decision.capture_width,
            ):
                return True

        self.current_encoder = None
        return False

    def _build_encoder_decision(self, input_format, rect, framerate) -> EncoderDecision:
        normalized_rect = self._normalize_rect(rect)
        capture_width = self._resolve_capture_width(normalized_rect)
        safe_framerate = self._resolve_safe_framerate(input_format, capture_width, framerate)
        candidates = tuple(self._encoder_candidates(capture_width, safe_framerate))
        return EncoderDecision(normalized_rect, capture_width, safe_framerate, candidates)

    def _normalize_rect(self, rect):
        if not rect:
            return None
        x1, y1, x2, y2 = rect
        left = min(x1, x2)
        top = min(y1, y2)
        width = max(2, abs(x2 - x1))
        height = max(2, abs(y2 - y1))
        width = width if width % 2 == 0 else width - 1
        height = height if height % 2 == 0 else height - 1
        return (left, top, left + width, top + height)

    def _resolve_capture_width(self, rect) -> int:
        if rect:
            return rect[2] - rect[0]
        width, _height = self._get_gdigrab_resolution()
        if width > 0:
            return width
        return self._system_width()

    @staticmethod
    def _system_width() -> int:
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
            return ctypes.windll.user32.GetSystemMetrics(0)
        except Exception:
            return 0

    @staticmethod
    def _resolve_safe_framerate(input_format, capture_width, framerate) -> int:
        if input_format == "gdigrab" and capture_width > 2560 and framerate > 60:
            print(f"High-Res Warning: Capping gdigrab FPS to 60 for stability (requested {framerate})")
            return 60
        return framerate

    def _encoder_candidates(self, capture_width: int, framerate: int) -> List[str]:
        if not USE_HARDWARE_ENCODER:
            return ["libx264"]

        available = set(self.get_available_encoders())
        candidates = [
            encoder
            for encoder in ENCODER_PRIORITY
            if encoder in available and self._is_encoder_compatible(encoder, capture_width, framerate)
        ]
        candidates.append("libx264")
        return candidates

    @staticmethod
    def _is_encoder_compatible(encoder: str, capture_width: int, framerate: int) -> bool:
        limits = ENCODER_LIMITS.get(encoder)
        if not limits:
            return True
        max_width = limits["max_width"]
        max_fps = limits["max_fps"]
        if max_width is not None and capture_width > max_width:
            return False
        return framerate <= max_fps

    def _build_ffmpeg_command(self, output_path, input_format, rect, mic, scene_plan, framerate, quality, encoder):
        capture_rects = self._capture_rects(rect, scene_plan)
        cmd = [FFMPEG_PATH, "-y"]
        cmd.extend(self._video_input_args(input_format, framerate, capture_rects))
        audio_index = len(capture_rects)
        if mic:
            cmd.extend(["-f", "dshow", "-i", f"audio={mic}"])
        cmd.extend(self._filter_args(scene_plan, capture_rects, mic is not None, audio_index))
        cmd.extend(["-c:v", encoder])
        cmd.extend(self._video_args(encoder, quality))
        cmd.extend(["-pix_fmt", "yuv420p", "-vsync", "cfr", output_path])
        return cmd

    @staticmethod
    def _capture_rects(rect, scene_plan):
        if scene_plan is None or not scene_plan.overlays:
            return [rect]

        rects = [scene_plan.primary_video.rect]
        rects.extend(layer.rect for layer in FFmpegHandler._overlay_layers(scene_plan))
        return rects

    def _video_input_args(self, input_format, framerate, capture_rects):
        args = []
        for rect in capture_rects:
            args.extend(["-f", input_format, "-framerate", str(framerate)])
            args.extend(self._build_capture_args(rect))
            args.extend(["-i", "desktop"])
        return args

    def _filter_args(self, scene_plan, capture_rects, has_mic, audio_index):
        filter_complex = self._video_filter_complex(scene_plan, capture_rects)
        if not filter_complex:
            return self._audio_filter_args(scene_plan, has_mic, audio_index)

        args = ["-filter_complex", filter_complex, "-map", "[vout]"]
        args.extend(self._mapped_audio_args(scene_plan, has_mic, audio_index))
        return args

    def _audio_filter_args(self, scene_plan, has_mic, audio_index):
        if scene_plan is None or not has_mic:
            return []

        mic_volume = self._microphone_volume(scene_plan)
        if mic_volume is None:
            return []
        return ["-filter:a", f"volume={mic_volume:.2f}"]

    def _mapped_audio_args(self, scene_plan, has_mic, audio_index):
        if not has_mic:
            return []
        args = ["-map", f"{audio_index}:a"]
        args.extend(self._audio_filter_args(scene_plan, has_mic, audio_index))
        return args

    @staticmethod
    def _microphone_volume(scene_plan):
        for channel in scene_plan.audio_channels:
            if channel.target and not channel.muted:
                return channel.volume
        return None

    def _video_filter_complex(self, scene_plan, capture_rects):
        if scene_plan is None or len(capture_rects) < 2:
            return ""

        base_rect = capture_rects[0]
        if base_rect is None:
            return ""
        chain = ["[0:v]setpts=PTS-STARTPTS[base0]"]
        current = "base0"
        overlays = self._overlay_layers(scene_plan)
        for index, layer in enumerate(overlays, start=1):
            overlay_name = f"ovr{index}"
            output_name = "vout" if index == len(capture_rects) - 1 else f"base{index}"
            chain.append(self._overlay_prepare(index, layer.opacity, overlay_name))
            chain.append(self._overlay_link(current, overlay_name, output_name, base_rect, capture_rects[index]))
            current = output_name
        if current != "vout":
            chain.append(f"[{current}]copy[vout]")
        return ";".join(chain)

    @staticmethod
    def _overlay_layers(scene_plan):
        return [layer for layer in scene_plan.overlays if layer.rect]

    @staticmethod
    def _overlay_prepare(index, opacity, overlay_name):
        if opacity >= 0.999:
            return f"[{index}:v]setpts=PTS-STARTPTS,format=rgba[{overlay_name}]"
        return (
            f"[{index}:v]setpts=PTS-STARTPTS,format=rgba,"
            f"colorchannelmixer=aa={opacity:.2f}[{overlay_name}]"
        )

    @staticmethod
    def _overlay_link(base_name, overlay_name, output_name, base_rect, overlay_rect):
        base_left = base_rect[0]
        base_top = base_rect[1]
        overlay_left = overlay_rect[0]
        overlay_top = overlay_rect[1]
        x_pos = overlay_left - base_left
        y_pos = overlay_top - base_top
        return f"[{base_name}][{overlay_name}]overlay={x_pos}:{y_pos}:format=auto[{output_name}]"

    @staticmethod
    def _build_capture_args(rect):
        if not rect:
            return []
        x1, y1, x2, y2 = rect
        return [
            "-offset_x", str(x1),
            "-offset_y", str(y1),
            "-video_size", f"{x2 - x1}x{y2 - y1}",
        ]

    @staticmethod
    def _video_args(encoder, quality):
        if encoder == "libx264":
            return ["-preset", quality["preset"], "-tune", "zerolatency", "-crf", str(quality["crf"])]
        if encoder == "h264_nvenc":
            return ["-preset", "p4", "-tune", "ll", "-rc", "vbr", "-cq", str(quality["crf"] + 5), "-b:v", "0"]
        if encoder == "h264_qsv":
            return ["-preset", "faster", "-global_quality", str(quality["crf"] + 5)]

        amf_qp = max(12, quality["crf"])
        return ["-usage", "lowlatency", "-rc", "cqp", "-qp_i", str(amf_qp), "-qp_p", str(amf_qp), "-quality", "speed"]

    def _launch_ffmpeg(self, cmd, output_path, encoder, framerate, safe_framerate, quality_preset, capture_width):
        self._open_log_file(output_path, encoder, framerate, safe_framerate, quality_preset, capture_width, cmd)
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            print(f"Failed to start FFmpeg with {encoder}: {e}")
            self._close_log_file()
            return False

        if self.process.poll() not in (None, 0):
            self.process = None
            self._close_log_file()
            return False

        self.current_encoder = encoder
        self._start_output_monitor()
        return True

    def _open_log_file(self, output_path, encoder, framerate, safe_framerate, quality_preset, capture_width, cmd):
        log_path = output_path + ".log"
        try:
            self._log_file = open(log_path, "w", encoding="utf-8")
            self._log_file.write(f"Encoder: {encoder}\n")
            self._log_file.write(f"FPS: {framerate}\n")
            self._log_file.write(f"Safe FPS: {safe_framerate}\n")
            self._log_file.write(f"Capture Width: {capture_width}\n")
            self._log_file.write(f"Quality: {quality_preset}\n")
            self._log_file.write(f"Command: {' '.join(cmd)}\n\n")
            self._log_file.flush()
        except Exception as e:
            print(f"Failed to create log file: {e}")
            self._log_file = None

    def _start_output_monitor(self):
        """Start thread to monitor FFmpeg output and parse progress"""
        def monitor():
            # Updated regex to handle FFmpeg's padded output format
            # Example: frame=   19 fps=0.0 q=-0.0 size=       0KiB time=00:00:00.63 bitrate=   0.6kbits/s speed=1.25x
            progress_pattern = re.compile(
                r'frame=\s*(\d+)\s+fps=\s*([\d.]+)\s+.*?size=\s*(\S+)\s+'
                r'time=(\S+)\s+bitrate=\s*([\d.]+\S*)'
            )
            speed_pattern = re.compile(r'speed=\s*([\d.]+x)')
            dropped_pattern = re.compile(r'drop\s*=\s*(\d+)', re.IGNORECASE)
            
            while self.process and self.process.poll() is None:
                try:
                    line = self.process.stderr.readline()
                    if not line:
                        continue
                    
                    # Try multiple encodings
                    for enc in ['utf-8', 'cp1251', 'cp866']:
                        try:
                            line_str = line.decode(enc).strip()
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        line_str = line.decode('utf-8', errors='ignore').strip()
                    
                    if not line_str:
                        continue
                    
                    # Log to file
                    if self._log_file:
                        try:
                            self._log_file.write(line_str + "\n")
                            self._log_file.flush()
                        except:
                            pass
                    
                    # Parse progress
                    match = progress_pattern.search(line_str)
                    if match:
                        speed = "N/A"
                        speed_match = speed_pattern.search(line_str)
                        if speed_match:
                            speed = speed_match.group(1)

                        self._last_progress = RecordingProgress(
                            frame=int(match.group(1)),
                            fps=float(match.group(2)),
                            size=match.group(3),
                            time=match.group(4),
                            bitrate=match.group(5),
                            speed=speed
                        )
                        
                        # Check for dropped frames
                        drop_match = dropped_pattern.search(line_str)
                        if drop_match:
                            self._last_progress.dropped = int(drop_match.group(1))
                        
                        # Call progress callback
                        if self._on_progress:
                            self._on_progress(self._last_progress)
                    
                    # Put in queue for external access
                    self._output_queue.put(line_str)
                    
                except Exception as e:
                    print(f"Monitor error: {e}")
                    break
            
            # Process ended - check for errors
            if self.process:
                returncode = self.process.returncode
                if returncode is not None and returncode != 0 and not self._is_paused:
                    # Read remaining stderr
                    try:
                        remaining = self.process.stderr.read()
                        if remaining and self._log_file:
                            self._log_file.write(remaining.decode('utf-8', errors='ignore'))
                    except:
                        pass
                    
                    if self._on_error:
                        self._on_error(f"FFmpeg exited with code {returncode}")
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def pause(self) -> bool:
        """
        Pause recording by cleanly stopping current segment.
        Much more reliable than NtSuspendProcess.
        """
        if not self._is_recording or self._is_paused or not self.process:
            return False
        
        # Stop current segment gracefully
        try:
            self.process.stdin.write(b"q")
            self.process.stdin.flush()
            self.process.wait(timeout=5)
        except Exception as e:
            print(f"Error stopping segment: {e}")
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                pass
        
        self._close_log_file()
        self.process = None
        
        self._is_paused = True
        self._pause_start = time.time()
        print(f"Recording paused (segment {self._segment_index - 1} saved)")
        return True

    def resume(self) -> bool:
        """Resume recording by starting a new segment"""
        if not self._is_recording or not self._is_paused:
            return False
        
        self._is_paused = False
        
        # Start new segment
        success = self._start_segment()
        if success:
            if self._pause_start:
                self._total_pause_duration += time.time() - self._pause_start
                self._pause_start = None
            print(f"Recording resumed (new segment {self._segment_index - 1})")
        else:
            self._is_paused = True
            print("Failed to resume recording")
            if self._on_error:
                self._on_error("Failed to resume recording")
        
        return success

    def toggle_pause(self) -> bool:
        """Toggle pause state, returns new pause state"""
        if self._is_paused:
            return not self.resume()

        if self.pause():
            return True

        return False

    def is_paused(self) -> bool:
        """Check if recording is paused"""
        return self._is_paused

    def stop_recording(self) -> Dict:
        """Stop recording and merge all segments"""
        duration = 0
        if self.start_timestamp:
            duration = time.time() - self.start_timestamp - self._total_pause_duration
        
        # If paused, no need to stop process (already stopped)
        if not self._is_paused and self.process:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
            self.process = None
        
        self._close_log_file()
        
        # Merge segments if multiple exist
        final_path = self._merge_segments()
        
        # Cleanup temp directory
        self._cleanup_temp()
        
        result = {
            "output_path": final_path,
            "duration": duration,
            "filename": os.path.basename(final_path) if final_path else None,
            "pause_duration": self._total_pause_duration,
            "segments_count": len(self._segments),
            "last_progress": self._last_progress
        }
        
        if self._on_stopped:
            self._on_stopped(result)
        
        # Reset state
        self._is_recording = False
        self._is_paused = False
        self.current_output = None
        self.current_encoder = None
        self.start_timestamp = None
        self._pause_start = None
        self._total_pause_duration = 0.0
        self._recording_params = None
        self._final_output = None
        self._segments = []
        self._segment_index = 0
        self._last_progress = RecordingProgress()
        
        return result

    def _merge_segments(self) -> Optional[str]:
        """Merge all segments into final output file"""
        if not self._segments:
            return None
        
        # Filter existing segments
        existing_segments = [s for s in self._segments if os.path.exists(s)]
        
        if not existing_segments:
            return None
        
        if len(existing_segments) == 1:
            # Only one segment - just move/copy it
            try:
                import shutil
                shutil.move(existing_segments[0], self._final_output)
                return self._final_output
            except Exception as e:
                print(f"Error moving segment: {e}")
                return existing_segments[0]
        
        # Multiple segments - use ffmpeg concat
        concat_file = os.path.join(self._temp_dir, "concat_list.txt")
        try:
            with open(concat_file, "w", encoding="utf-8") as f:
                for segment in existing_segments:
                    # Escape single quotes in path
                    safe_path = segment.replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
            
            # Run concat
            cmd = [
                FFMPEG_PATH, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                self._final_output
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=300
            )
            
            if result.returncode == 0 and os.path.exists(self._final_output):
                print(f"Merged {len(existing_segments)} segments successfully")
                return self._final_output
            else:
                print(f"Merge failed: {result.stderr.decode('utf-8', errors='ignore')}")
                return existing_segments[-1]  # Return last segment as fallback
                
        except Exception as e:
            print(f"Error merging segments: {e}")
            return existing_segments[-1] if existing_segments else None

    def _cleanup_temp(self):
        """Clean up temporary segment files"""
        if not self._temp_dir:
            return
        
        try:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning temp dir: {e}")
        
        self._temp_dir = None

    def _close_log_file(self):
        """Safely close log file"""
        if self._log_file:
            try:
                self._log_file.close()
            except:
                pass
            self._log_file = None

    def get_elapsed_time(self) -> float:
        """Get elapsed recording time (excluding pauses)"""
        if not self.start_timestamp:
            return 0
        
        elapsed = time.time() - self.start_timestamp - self._total_pause_duration
        
        if self._is_paused and self._pause_start:
            elapsed -= (time.time() - self._pause_start)
        
        return max(0, elapsed)

    def get_progress(self) -> RecordingProgress:
        """Get last known progress data"""
        return self._last_progress

    def get_output_lines(self, max_lines: int = 100) -> List[str]:
        """Get recent FFmpeg output lines"""
        lines = []
        while not self._output_queue.empty() and len(lines) < max_lines:
            try:
                lines.append(self._output_queue.get_nowait())
            except queue.Empty:
                break
        return lines

    def get_dshow_audio_names(self) -> List[str]:
        """Parse audio device names directly from FFmpeg dshow list"""
        device_names = []
        try:
            # -f dshow -i dummy lists devices. stderr contains the list.
            cmd = [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                encoding='utf-8', 
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            output = result.stderr
            lines = output.split('\n')
            
            is_audio_section = False
            for line in lines:
                if "DirectShow audio devices" in line:
                    is_audio_section = True
                    continue
                
                if "DirectShow video devices" in line:
                    is_audio_section = False
                    break
                
                if is_audio_section and line.strip().startswith('[dshow') and '"' in line:
                    # Extract name in quotes: [dshow @ ...]  "Microphone (Realtek)"
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        name = match.group(1)
                        # Filter out alternative names and duplicates
                        if not name.startswith("@device") and name not in device_names:
                            device_names.append(name)
                            
        except Exception as e:
            print(f"Error parsing dshow devices: {e}")
            
        return device_names
