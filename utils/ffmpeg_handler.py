
"""
Async FFmpeg Handler for NeoRecorder.
Non-blocking subprocess management for smooth UI experience.
"""

import subprocess
import os
import time
import threading
import queue
from typing import Optional, Dict, Callable
from config import FFMPEG_PATH, QUALITY_PRESETS, USE_HARDWARE_ENCODER

class FFmpegHandler:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.current_output: Optional[str] = None
        self.start_timestamp: Optional[float] = None
        self._available_encoders: Optional[list] = None
        
        # Async management
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_paused = False
        self._pause_start: Optional[float] = None
        self._total_pause_duration: float = 0.0
        
        # Callbacks
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_started: Optional[Callable[[], None]] = None
        self._on_stopped: Optional[Callable[[Dict], None]] = None
        
        # Output monitoring
        self._output_queue = queue.Queue()
        self._monitor_thread: Optional[threading.Thread] = None

    def set_callbacks(self, on_started=None, on_stopped=None, on_error=None):
        """Set callback functions for async events"""
        self._on_started = on_started
        self._on_stopped = on_stopped
        self._on_error = on_error

    def get_available_encoders(self):
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
            
            # Check for hardware encoders
            if "h264_nvenc" in output:
                self._available_encoders.append("h264_nvenc")  # NVIDIA
            if "h264_qsv" in output:
                self._available_encoders.append("h264_qsv")    # Intel Quick Sync
            if "h264_amf" in output:
                self._available_encoders.append("h264_amf")    # AMD AMF
            if "hevc_nvenc" in output:
                self._available_encoders.append("hevc_nvenc")
                
        except Exception as e:
            print(f"Error detecting encoders: {e}")
        
        return self._available_encoders

    def get_best_encoder(self):
        """Get the best available encoder (prefer hardware)"""
        if not USE_HARDWARE_ENCODER:
            return "libx264"
        
        encoders = self.get_available_encoders()
        priority = ["h264_nvenc", "h264_qsv", "h264_amf"]
        
        for enc in priority:
            if enc in encoders:
                return enc
        
        return "libx264"  # Fallback to software

    def start_recording_async(self, output_path, rect=None, mic=None, system=False,
                              framerate=60, quality_preset="balanced"):
        """
        Start recording in a separate thread (non-blocking).
        Use set_callbacks() to receive events.
        """
        self._stop_event.clear()
        self._is_paused = False
        self._total_pause_duration = 0.0
        
        self._worker_thread = threading.Thread(
            target=self._recording_worker,
            args=(output_path, rect, mic, system, framerate, quality_preset),
            daemon=True
        )
        self._worker_thread.start()

    def _recording_worker(self, output_path, rect, mic, system, framerate, quality_preset):
        """Worker thread for recording"""
        self.current_output = output_path
        self.start_timestamp = time.time()
        
        # Try ddagrab first
        success = self._try_ffmpeg(output_path, "ddagrab", rect, mic, system, 
                                   framerate, quality_preset)
        
        if not success:
            print("ddagrab failed, falling back to gdigrab...")
            fallback_fps = min(framerate, 60)
            success = self._try_ffmpeg(output_path, "gdigrab", rect, mic, system,
                                       fallback_fps, quality_preset)
        
        if success and self._on_started:
            self._on_started()
        elif not success and self._on_error:
            self._on_error("Failed to start recording")

    def start_recording(self, output_path, rect=None, mic=None, system=False,
                       framerate=60, quality_preset="balanced"):
        """
        Start recording synchronously (for backward compatibility).
        """
        self.current_output = output_path
        self.start_timestamp = time.time()
        self._is_paused = False
        self._total_pause_duration = 0.0
        
        success = self._try_ffmpeg(output_path, "ddagrab", rect, mic, system, 
                                   framerate, quality_preset)
        
        if not success:
            print("ddagrab failed, falling back to gdigrab...")
            fallback_fps = min(framerate, 60)
            self._try_ffmpeg(output_path, "gdigrab", rect, mic, system,
                           fallback_fps, quality_preset)

    def _try_ffmpeg(self, output_path, input_format, rect, mic, system,
                   framerate, quality_preset):
        """Build and execute FFmpeg command"""
        
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

        # Video encoding options
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

        # Log command
        log_path = output_path + ".log"
        self.log_file = open(log_path, "w", encoding="utf-8")
        self.log_file.write(f"Encoder: {encoder}\n")
        self.log_file.write(f"FPS: {framerate}\n")
        self.log_file.write(f"Quality: {quality_preset}\n")
        self.log_file.write(f"Command: {' '.join(cmd)}\n")
        self.log_file.flush()
        
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=self.log_file, 
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"Failed to start FFmpeg: {e}")
            self.log_file.close()
            return False
        
        # Start output monitor thread
        self._start_output_monitor()
        
        # Give it a moment to see if it crashes
        time.sleep(0.5)
        if self.process.poll() is not None:
            self.log_file.close()
            self.process = None
            return False
            
        return True

    def _start_output_monitor(self):
        """Start a thread to monitor FFmpeg output for errors"""
        def monitor():
            while self.process and self.process.poll() is None:
                time.sleep(0.1)
            
            # Process ended
            if self.process and self.process.returncode != 0:
                if self._on_error:
                    self._on_error(f"FFmpeg exited with code {self.process.returncode}")
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def pause(self):
        """
        Pause recording by suspending the FFmpeg process.
        Note: This works on Windows using NtSuspendProcess/NtResumeProcess via ctypes.
        """
        if not self.process or self._is_paused:
            return False
        
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            
            # Get process handle with PROCESS_SUSPEND_RESUME access
            PROCESS_SUSPEND_RESUME = 0x0800
            handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, self.process.pid)
            
            if handle:
                # Use NtSuspendProcess from ntdll
                ntdll = ctypes.windll.ntdll
                ntdll.NtSuspendProcess(handle)
                kernel32.CloseHandle(handle)
                
                self._is_paused = True
                self._pause_start = time.time()
                print("Recording paused")
                return True
        except Exception as e:
            print(f"Pause failed: {e}")
        
        return False

    def resume(self):
        """Resume paused recording"""
        if not self.process or not self._is_paused:
            return False
        
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            
            PROCESS_SUSPEND_RESUME = 0x0800
            handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, self.process.pid)
            
            if handle:
                ntdll = ctypes.windll.ntdll
                ntdll.NtResumeProcess(handle)
                kernel32.CloseHandle(handle)
                
                if self._pause_start:
                    self._total_pause_duration += time.time() - self._pause_start
                
                self._is_paused = False
                self._pause_start = None
                print("Recording resumed")
                return True
        except Exception as e:
            print(f"Resume failed: {e}")
        
        return False

    def toggle_pause(self):
        """Toggle pause state"""
        if self._is_paused:
            return self.resume()
        else:
            return self.pause()

    def is_paused(self):
        """Check if recording is paused"""
        return self._is_paused

    def stop_recording(self):
        """Stop recording and return metadata"""
        duration = 0
        if self.start_timestamp:
            duration = time.time() - self.start_timestamp - self._total_pause_duration
        
        # If paused, resume first to allow clean shutdown
        if self._is_paused:
            self.resume()
            
        if self.process:
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
            
            if hasattr(self, 'log_file') and self.log_file:
                self.log_file.close()
                self.log_file = None
        
        result = {
            "output_path": self.current_output,
            "duration": duration,
            "filename": os.path.basename(self.current_output) if self.current_output else None,
            "pause_duration": self._total_pause_duration
        }
        
        # Call callback if set
        if self._on_stopped:
            self._on_stopped(result)
        
        self.current_output = None
        self.start_timestamp = None
        self._total_pause_duration = 0.0
        
        return result

    def get_elapsed_time(self):
        """Get elapsed recording time (excluding pauses)"""
        if not self.start_timestamp:
            return 0
        
        elapsed = time.time() - self.start_timestamp - self._total_pause_duration
        
        if self._is_paused and self._pause_start:
            elapsed -= (time.time() - self._pause_start)
        
        return max(0, elapsed)

    @staticmethod
    def get_audio_devices():
        """Get list of audio devices via FFmpeg dshow"""
        try:
            cmd = [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, 
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            
            for enc in ['utf-8', 'cp1251', 'cp866']:
                try:
                    return result.stderr.decode(enc)
                except UnicodeDecodeError:
                    continue
            return result.stderr.decode('utf-8', errors='ignore')
        except:
            return ""
