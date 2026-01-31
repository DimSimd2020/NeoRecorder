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


class FFmpegHandler:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.current_output: Optional[str] = None
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

    def get_available_encoders(self) -> List[str]:
        """Detect available hardware encoders (cached)"""
        if self._available_encoders is not None:
            return self._available_encoders
        
        self._available_encoders = []
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-encoders", "-hide_banner"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout
            
            if "h264_nvenc" in output:
                self._available_encoders.append("h264_nvenc")
            if "h264_qsv" in output:
                self._available_encoders.append("h264_qsv")
            if "h264_amf" in output:
                self._available_encoders.append("h264_amf")
            if "hevc_nvenc" in output:
                self._available_encoders.append("hevc_nvenc")
                
        except Exception as e:
            print(f"Error detecting encoders: {e}")
        
        return self._available_encoders

    def get_best_encoder(self) -> str:
        """Get the best available encoder (prefer hardware)"""
        if not USE_HARDWARE_ENCODER:
            return "libx264"
        
        encoders = self.get_available_encoders()
        priority = ["h264_nvenc", "h264_qsv", "h264_amf"]
        
        for enc in priority:
            if enc in encoders:
                return enc
        
        return "libx264"

    def start_recording(self, output_path: str, rect=None, mic=None, system=False,
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
            "framerate": framerate,
            "quality_preset": quality_preset
        }
        
        self.start_timestamp = time.time()
        
        # Start first segment
        return self._start_segment()

    def _start_segment(self) -> bool:
        """Start a new recording segment"""
        if not self._temp_dir or not self._recording_params:
            return False
        
        # Generate segment filename
        segment_path = os.path.join(
            self._temp_dir, 
            f"segment_{self._segment_index:04d}.mp4"
        )
        self._segments.append(segment_path)
        self.current_output = segment_path
        
        params = self._recording_params
        success = self._try_ffmpeg(
            segment_path,
            "ddagrab",
            params["rect"],
            params["mic"],
            params["system"],
            params["framerate"],
            params["quality_preset"]
        )
        
        if not success:
            print("ddagrab failed, falling back to gdigrab...")
            fallback_fps = min(params["framerate"], 60)
            success = self._try_ffmpeg(
                segment_path,
                "gdigrab",
                params["rect"],
                params["mic"],
                params["system"],
                fallback_fps,
                params["quality_preset"]
            )
        
        if success:
            self._is_recording = True
            self._segment_index += 1
            if self._on_started:
                self._on_started()
        
        return success

    def _try_ffmpeg(self, output_path: str, input_format: str, rect, mic, 
                   system, framerate, quality_preset) -> bool:
        """Build and execute FFmpeg command with proper resource management"""
        
        quality = QUALITY_PRESETS.get(quality_preset, QUALITY_PRESETS["balanced"])
        encoder = self.get_best_encoder()
        
        cmd = [FFMPEG_PATH, "-y"]
        
        # Input options
        cmd.extend(["-f", input_format])
        cmd.extend(["-framerate", str(framerate)])
        
        # Region capture
        if rect:
            x, y, x2, y2 = rect
            w, h = x2 - x, y2 - y
            # Ensure even dimensions
            w = w if w % 2 == 0 else w - 1
            h = h if h % 2 == 0 else h - 1
            cmd.extend([
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}"
            ])
            
        cmd.extend(["-i", "desktop"])

        # Microphone input
        if mic:
            cmd.extend(["-f", "dshow", "-i", f"audio={mic}"])

        # Video encoding
        cmd.extend(["-c:v", encoder])
        
        if encoder == "libx264":
            cmd.extend([
                "-preset", quality["preset"],
                "-tune", "zerolatency",
                "-crf", str(quality["crf"]),
            ])
        elif encoder == "h264_nvenc":
            cmd.extend([
                "-preset", "p4",
                "-tune", "ll",
                "-rc", "vbr",
                "-cq", str(quality["crf"] + 5),
                "-b:v", "0",
            ])
        elif encoder == "h264_qsv":
            cmd.extend([
                "-preset", "faster",
                "-global_quality", str(quality["crf"] + 5),
            ])
        elif encoder == "h264_amf":
            cmd.extend([
                "-quality", "speed",
                "-rc", "cqp",
                "-qp_i", str(quality["crf"]),
                "-qp_p", str(quality["crf"]),
            ])
        
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-vsync", "cfr",
        ])
        
        cmd.append(output_path)

        # Setup logging
        log_path = output_path + ".log"
        try:
            self._log_file = open(log_path, "w", encoding="utf-8")
            self._log_file.write(f"Encoder: {encoder}\n")
            self._log_file.write(f"FPS: {framerate}\n")
            self._log_file.write(f"Quality: {quality_preset}\n")
            self._log_file.write(f"Command: {' '.join(cmd)}\n\n")
            self._log_file.flush()
        except Exception as e:
            print(f"Failed to create log file: {e}")
            self._log_file = None
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"Failed to start FFmpeg: {e}")
            self._close_log_file()
            return False
        
        # Start progress monitor
        self._start_output_monitor()
        
        return True

    def _start_output_monitor(self):
        """Start thread to monitor FFmpeg output and parse progress"""
        def monitor():
            progress_pattern = re.compile(
                r'frame=\s*(\d+)\s+fps=\s*([\d.]+)\s+.*?size=\s*(\S+)\s+'
                r'time=(\S+)\s+bitrate=\s*(\S+)\s+.*?speed=\s*(\S+)'
            )
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
                        self._last_progress = RecordingProgress(
                            frame=int(match.group(1)),
                            fps=float(match.group(2)),
                            size=match.group(3),
                            time=match.group(4),
                            bitrate=match.group(5),
                            speed=match.group(6)
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
        
        # Track pause duration
        if self._pause_start:
            self._total_pause_duration += time.time() - self._pause_start
            self._pause_start = None
        
        self._is_paused = False
        
        # Start new segment
        success = self._start_segment()
        if success:
            print(f"Recording resumed (new segment {self._segment_index - 1})")
        else:
            print("Failed to resume recording")
            if self._on_error:
                self._on_error("Failed to resume recording")
        
        return success

    def toggle_pause(self) -> bool:
        """Toggle pause state, returns new pause state"""
        if self._is_paused:
            self.resume()
            return False
        else:
            self.pause()
            return True

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
        self.start_timestamp = None
        self._total_pause_duration = 0.0
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

    @staticmethod
    def get_audio_devices() -> str:
        """Get list of audio devices via FFmpeg dshow"""
        try:
            cmd = [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # FFmpeg outputs device list to stderr
            for enc in ['utf-8', 'cp1251', 'cp866']:
                try:
                    return result.stderr.decode(enc)
                except UnicodeDecodeError:
                    continue
            return result.stderr.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error getting audio devices: {e}")
            return ""
