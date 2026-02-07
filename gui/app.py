
import json
import os
import threading
import time
import customtkinter as ctk
from PIL import Image
from config import *
from core.audio_manager import AudioManager
from core.window_finder import WindowFinder
from core.recorder import ScreenRecorder
from gui.widgets import VUMeter
from gui.overlay import RegionOverlay
from gui.recording_widget import RecordingWidget
from gui.tray import SystemTray
from gui.quick_overlay import QuickOverlay
from utils.notifications import show_recording_complete, show_simple_notification
from utils.hotkeys import get_hotkey_manager
from utils.screenshot import get_screenshot_capture
from utils.logger import get_logger

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(parent.t("settings"))
        self.geometry("480x650")
        self.configure(fg_color=BG_COLOR)
        self.attributes("-topmost", True)
        
        self.setup_ui()

    def setup_ui(self):
        # Title
        ctk.CTkLabel(self, text=self.parent.t("settings"), 
                    font=("Segoe UI", 22, "bold"), 
                    text_color=NEON_BLUE).pack(pady=15)
        
        # Scrollable frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        # === Language Section ===
        lang_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        lang_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(lang_frame, text="Language / Язык:", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        self.lang_combo = ctk.CTkComboBox(lang_frame, values=["ru", "en"], 
                                          width=200, command=self.change_lang)
        self.lang_combo.set(self.parent.current_lang)
        self.lang_combo.pack(pady=(0, 12), padx=15, anchor="w")

        # === Recording Settings ===
        rec_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        rec_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(rec_frame, text="🎬 " + self.parent.t("fps") + ":", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        fps_values = [str(f) for f in FPS_OPTIONS]
        self.fps_combo = ctk.CTkComboBox(rec_frame, values=fps_values, width=200)
        self.fps_combo.set(str(self.parent.current_fps))
        self.fps_combo.pack(pady=(0, 10), padx=15, anchor="w")
        
        ctk.CTkLabel(rec_frame, text=self.parent.t("quality") + ":", 
                    font=("Segoe UI", 12, "bold")).pack(pady=5, padx=15, anchor="w")
        
        lang_key = "label_ru" if self.parent.current_lang == "ru" else "label_en"
        quality_labels = [QUALITY_PRESETS[k][lang_key] for k in QUALITY_PRESETS]
        self.quality_keys = list(QUALITY_PRESETS.keys())
        
        self.quality_combo = ctk.CTkComboBox(rec_frame, values=quality_labels, width=200)
        current_idx = self.quality_keys.index(self.parent.current_quality)
        self.quality_combo.set(quality_labels[current_idx])
        self.quality_combo.pack(pady=(0, 10), padx=15, anchor="w")
        
        # Encoder info
        encoder = self.parent.recorder.get_best_encoder()
        encoder_label = "GPU (NVENC)" if "nvenc" in encoder else \
                       "GPU (QuickSync)" if "qsv" in encoder else \
                       "GPU (AMF)" if "amf" in encoder else "CPU (x264)"
        
        ctk.CTkLabel(rec_frame, text=f"{self.parent.t('encoder')}: {encoder_label}", 
                    font=("Segoe UI", 11), text_color=SECONDARY_TEXT_COLOR).pack(pady=(0, 12), padx=15, anchor="w")

        # === Output Path ===
        path_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        path_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(path_frame, text="📁 " + self.parent.t("output_path") + ":", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        path_row = ctk.CTkFrame(path_frame, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 12))
        
        self.path_entry = ctk.CTkEntry(path_row, width=300, height=35)
        self.path_entry.insert(0, self.parent.recorder.get_output_dir())
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_btn = ctk.CTkButton(path_row, text="...", 
                                        width=50, height=35, command=self.browse_path)
        self.browse_btn.pack(side="right")

        # === Tray Settings ===
        tray_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        tray_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(tray_frame, text="🔔 Фоновый режим:", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        self.tray_switch = ctk.CTkSwitch(
            tray_frame, 
            text="Сворачивать в трей при закрытии",
            font=("Segoe UI", 11)
        )
        self.tray_switch.pack(pady=5, padx=15, anchor="w")
        if settings.get("minimize_to_tray", True):
            self.tray_switch.select()
        
        self.start_min_switch = ctk.CTkSwitch(
            tray_frame, 
            text="Запускать свёрнутым",
            font=("Segoe UI", 11)
        )
        self.start_min_switch.pack(pady=(5, 12), padx=15, anchor="w")
        if settings.get("start_minimized", False):
            self.start_min_switch.select()

        # === Hotkeys Section ===
        hotkey_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        hotkey_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(hotkey_frame, text="⌨️ Горячие клавиши:", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        # Quick overlay hotkey
        hk_row1 = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hk_row1.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(hk_row1, text="Быстрый захват:", width=150,
                    font=("Segoe UI", 11)).pack(side="left")
        self.quick_hotkey_entry = ctk.CTkEntry(hk_row1, width=150, height=32)
        self.quick_hotkey_entry.insert(0, settings.get_hotkey("quick_overlay"))
        self.quick_hotkey_entry.pack(side="left", padx=10)
        
        # Show window hotkey
        hk_row2 = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hk_row2.pack(fill="x", padx=15, pady=(5, 12))
        
        ctk.CTkLabel(hk_row2, text="Показать окно:", width=150,
                    font=("Segoe UI", 11)).pack(side="left")
        self.show_hotkey_entry = ctk.CTkEntry(hk_row2, width=150, height=32)
        self.show_hotkey_entry.insert(0, settings.get_hotkey("show_window"))
        self.show_hotkey_entry.pack(side="left", padx=10)

        # === Screenshots Path ===
        scr_path_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        scr_path_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(scr_path_frame, text="📸 " + self.parent.t("screenshots_path") + ":", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        scr_path_row = ctk.CTkFrame(scr_path_frame, fg_color="transparent")
        scr_path_row.pack(fill="x", padx=15, pady=(0, 12))
        
        self.scr_path_entry = ctk.CTkEntry(scr_path_row, width=300, height=35)
        self.scr_path_entry.insert(0, settings.get("screenshots_dir", SCREENSHOTS_DIR))
        self.scr_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_scr_btn = ctk.CTkButton(scr_path_row, text="...", 
                                        width=50, height=35, command=self.browse_screenshots)
        self.browse_scr_btn.pack(side="right")

        # === Overlay Settings ===
        ovr_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", corner_radius=10)
        ovr_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(ovr_frame, text="🎨 " + self.parent.t("overlay_settings") + ":", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        
        self.ovr_dim_switch = ctk.CTkSwitch(
            ovr_frame, 
            text=self.parent.t("dim_screen"),
            font=("Segoe UI", 11)
        )
        self.ovr_dim_switch.pack(pady=5, padx=15, anchor="w")
        if settings.get("overlay_dim_screen", True):
            self.ovr_dim_switch.select()
            
        self.ovr_lock_switch = ctk.CTkSwitch(
            ovr_frame, 
            text=self.parent.t("lock_input"),
            font=("Segoe UI", 11)
        )
        self.ovr_lock_switch.pack(pady=(5, 12), padx=15, anchor="w")
        if settings.get("overlay_lock_input", True):
            self.ovr_lock_switch.select()

        # === Save Button ===
        save_btn = ctk.CTkButton(self, text="Сохранить", width=140, height=40, 
                                 fg_color=ACCENT_COLOR, command=self.save_and_close)
        save_btn.pack(pady=15)

    def browse_path(self):
        new_path = ctk.filedialog.askdirectory(initialdir=self.parent.recorder.get_output_dir())
        if new_path:
            self.parent.recorder.set_output_dir(new_path)
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, new_path)

    def browse_screenshots(self):
        new_path = ctk.filedialog.askdirectory(initialdir=settings.get("screenshots_dir", SCREENSHOTS_DIR))
        if new_path:
            self.scr_path_entry.delete(0, "end")
            self.scr_path_entry.insert(0, new_path)

    def change_lang(self, new_lang):
        self.parent.change_language(new_lang)
        self.destroy()

    def save_and_close(self):
        # Save FPS
        try:
            fps = int(self.fps_combo.get())
            self.parent.current_fps = fps
            self.parent.recorder.set_fps(fps)
            settings.set("fps", fps)
        except ValueError:
            pass
        
        # Save Quality
        lang_key = "label_ru" if self.parent.current_lang == "ru" else "label_en"
        selected_label = self.quality_combo.get()
        for key, preset in QUALITY_PRESETS.items():
            if preset[lang_key] == selected_label:
                self.parent.current_quality = key
                self.parent.recorder.set_quality(key)
                settings.set("quality", key)
                break
        
        # Save path
        new_path = self.path_entry.get()
        if new_path and os.path.exists(new_path):
            self.parent.recorder.set_output_dir(new_path)
            settings.set("output_dir", new_path)
        
        # Save tray settings
        settings.set("minimize_to_tray", self.tray_switch.get())
        settings.set("start_minimized", self.start_min_switch.get())
        
        # Save hotkeys
        quick_key = self.quick_hotkey_entry.get().strip()
        show_key = self.show_hotkey_entry.get().strip()
        
        if quick_key:
            settings.set_hotkey("quick_overlay", quick_key)
        if show_key:
            settings.set_hotkey("show_window", show_key)
        
        # Save screenshot path
        scr_path = self.scr_path_entry.get()
        if scr_path and os.path.exists(scr_path):
            self.parent.screenshot_capture.set_output_dir(scr_path)
            settings.set("screenshots_dir", scr_path)
        
        # Save overlay settings
        settings.set("overlay_dim_screen", self.ovr_dim_switch.get())
        settings.set("overlay_lock_input", self.ovr_lock_switch.get())

        # Re-register hotkeys
        self.parent._register_hotkeys()
        
        self.destroy()

class NeoRecorderApp(ctk.CTk):
    def __init__(self):
        # Fix taskbar icon grouping and display
        try:
            import ctypes
            myappid = f'dimsimd.neorecorder.app.{VERSION}' # Arbitrary unique ID
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass
            
        super().__init__()

        self.title(APP_NAME)
        self.geometry("420x650")
        self.configure(fg_color=BG_COLOR)
        
        # Set window icon
        try:
            icon_path = resource_path("app_icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
            
        # 1. Show Loading Screen immediately
        self.loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self.loading_frame, text="NeoRecorder", font=("Segoe UI", 32, "bold"), text_color=NEON_BLUE).pack(pady=10)
        ctk.CTkLabel(self.loading_frame, text="Loading...", font=("Segoe UI", 16)).pack()
        
        # Force window to render "Loading..." before we freeze it with initialization
        self.update()
        
        # 2. Synchronous Initialization
        try:
            self._init_components()
            
            # 3. Build UI
            self.loading_frame.destroy()
            self.setup_ui()
            
            # 4. Final adjustments
            self._register_hotkeys()
            
            if self._settings.get("minimize_to_tray", True):
                self._init_tray()
                
            if self._settings.get("start_minimized", False):
                self._minimize_to_tray()
                
        except Exception as e:
            # If init fails, show error
            print(f"Startup Error: {e}")
            self.loading_frame.destroy()
            ctk.CTkLabel(self, text=f"Error starting app:\n{e}", text_color="red").pack(expand=True)

    def _init_components(self):
        """Initialize all backend components"""
        self._logger = get_logger()
        
        # Load settings
        self._settings = settings
        self.current_lang = self._settings.get("language", DEFAULT_LANG)
        self.current_fps = self._settings.get("fps", DEFAULT_FPS)
        self.current_quality = self._settings.get("quality", DEFAULT_QUALITY)
        
        # Load language
        self.lang_data = self._load_lang(self.current_lang)
        
        # Initialize Core Components
        # We do this synchronously now to avoid threading issues
        self.audio_manager = AudioManager()
        self.window_finder = WindowFinder()
        self.recorder = ScreenRecorder()
        
        # Apply save settings to recorder
        self.recorder.set_fps(self.current_fps)
        self.recorder.set_quality(self.current_quality)
        saved_path = self._settings.get("output_dir")
        if saved_path:
            self.recorder.set_output_dir(saved_path)
            
        self.screenshot_capture = get_screenshot_capture()
        self.hotkey_manager = get_hotkey_manager()
        
        # Register recorder callbacks
        self.recorder.set_callbacks(
            on_error=self.on_recording_error,
            on_complete=self.on_recording_complete_event,
            on_warning=self.on_recording_warning
        )
        
        # State
        self.recording_mode = self._settings.get("last_mode", "screen")
        self.selected_rect = None
        self.selected_window_hwnd = None
        self.active_windows = []
        self.widget = None
        self.quick_overlay = None
        self.tray = None

    def on_recording_warning(self, message):
        """Handle recording warning from backend"""
        from utils.notifications import show_warning_notification
        self.after(0, lambda: show_warning_notification("Note", message))

    def on_recording_error(self, error):
        """Handle recording error from backend"""
        self.after(0, lambda: self._handle_recording_error_ui(error))
        
    def _handle_recording_error_ui(self, error):
        # Stop UI state
        if hasattr(self, 'widget') and self.widget:
            self.widget.destroy()
            self.widget = None
        
        self.deiconify()
        self.rec_btn.configure(image=self.icon_rec, fg_color="transparent")
        self.timer_label.configure(text="00:00:00")
        
        from utils.notifications import show_simple_notification
        show_simple_notification("Recording Error", str(error))
        
    def on_recording_complete_event(self, result):
        """Handle async recording stop (e.g. from hotkey or error recovery)"""
        # This might be called when we stop manually too, so check state
        pass

    def _init_tray(self):
        """Initialize system tray"""
        try:
            self.tray = SystemTray(
                on_show=self._show_from_tray,
                on_quick_capture=self._open_quick_overlay,
                on_quit=self._quit_app
            )
            self.tray.start()
        except Exception as e:
            self._logger.error(f"Failed to init tray: {e}")

    def _register_hotkeys(self):
        """Register global hotkeys"""
        try:
            self.hotkey_manager.unregister_all()
            
            quick_key = self._settings.get_hotkey("quick_overlay")
            if quick_key:
                self.hotkey_manager.register(quick_key, self._open_quick_overlay_threadsafe, "quick_overlay")
            
            show_key = self._settings.get_hotkey("show_window")
            if show_key:
                self.hotkey_manager.register(show_key, self._show_from_tray_threadsafe, "show_window")
        except Exception as e:
            self._logger.error(f"Failed to register hotkeys: {e}")

    def _open_quick_overlay_threadsafe(self):
        self.after(0, self._open_quick_overlay)
    
    def _show_from_tray_threadsafe(self):
        self.after(0, self._show_from_tray)

    def _load_lang(self, lang):
        path = os.path.join(LANG_DIR, f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def t(self, key):
        return self.lang_data.get(key, key)

    def change_language(self, lang):
        self.current_lang = lang
        self.lang_data = self._load_lang(lang)
        for widget in self.winfo_children():
            widget.destroy()
        self.setup_ui()

    def open_settings(self):
        SettingsWindow(self)

    def setup_ui(self):
        # Load Icons
        self.icon_rec = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "rec.png")), size=(80, 80))
        self.icon_stop = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "stop.png")), size=(80, 80))
        self.icon_folder = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "folder.png")), size=(30, 30))
        self.icon_settings = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "settings.png")), size=(30, 30))

        # Header
        self.header = ctk.CTkLabel(self, text=self.t("app_title"), 
                                   font=("Segoe UI", 28, "bold"), text_color=NEON_BLUE)
        self.header.pack(pady=20)

        # Mode Selection
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.mode_frame.pack(pady=10)
        
        self.btn_screen = ctk.CTkButton(self.mode_frame, text=self.t("mode_screen"), 
                                        width=100, command=lambda: self.set_mode("screen"))
        self.btn_screen.grid(row=0, column=0, padx=5)
        
        self.btn_region = ctk.CTkButton(self.mode_frame, text=self.t("mode_region"), 
                                        width=100, command=self.select_region)
        self.btn_region.grid(row=0, column=1, padx=5)
        
        self.btn_window = ctk.CTkButton(self.mode_frame, text=self.t("mode_window"), 
                                        width=100, command=self.show_window_selector)
        self.btn_window.grid(row=0, column=2, padx=5)

        # Window Selection Dropdown (hidden by default)
        self.window_combo = ctk.CTkComboBox(self, width=380, command=self.on_window_selected)
        self.window_combo.pack(pady=5)
        self.window_combo.pack_forget()

        # FPS/Quality indicator
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(pady=5)
        
        encoder = self.recorder.get_best_encoder()
        encoder_short = "NVENC" if "nvenc" in encoder else \
                       "QSV" if "qsv" in encoder else \
                       "AMF" if "amf" in encoder else "CPU"
        
        self.fps_label = ctk.CTkLabel(self.status_frame, 
                                      text=f"{self.current_fps} FPS | {encoder_short}", 
                                      font=("Segoe UI", 11), text_color=SECONDARY_TEXT_COLOR)
        self.fps_label.pack()

        # Audio Section
        self.audio_frame = ctk.CTkFrame(self, fg_color="#333333", corner_radius=10)
        self.audio_frame.pack(pady=20, padx=20, fill="x")
        
        self.mic_switch = ctk.CTkSwitch(self.audio_frame, text=self.t("mic_source"), 
                                        progress_color=NEON_BLUE)
        self.mic_switch.pack(pady=10, padx=10, anchor="w")
        
        self.device_names = []
        self.device_combo = ctk.CTkComboBox(self.audio_frame, values=[self.t("loading")], width=340)
        self.device_combo.pack(pady=5, padx=10)
        self.device_combo.set(self.t("loading"))

        # Defer audio LISTING to thread (it is safe to do in background as it just enumerates)
        threading.Thread(target=self._load_audio_devices_thread, daemon=True).start()
        
        self.vu_meter = VUMeter(self.audio_frame, width=360, height=8)
        self.vu_meter.pack(pady=10, padx=10)

        self.sys_audio_switch = ctk.CTkSwitch(self.audio_frame, text=self.t("system_source"), 
                                              progress_color=NEON_BLUE)
        self.sys_audio_switch.pack(pady=10, padx=10, anchor="w")

        # Record Button
        self.rec_btn = ctk.CTkButton(self, text="", image=self.icon_rec,
                                     fg_color="transparent", hover_color="#333333",
                                     width=120, height=120, corner_radius=60,
                                     command=self.toggle_record)
        self.rec_btn.pack(pady=30)

        # Bottom Buttons
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(fill="x", side="bottom", pady=10)
        
        self.btn_folder = ctk.CTkButton(self.bottom_frame, text="", image=self.icon_folder, 
                                        width=40, command=self.open_folder, fg_color="transparent")
        self.btn_folder.pack(side="left", padx=20)
        
        self.timer_label = ctk.CTkLabel(self.bottom_frame, text="00:00:00", font=("Consolas", 18))
        self.timer_label.pack(side="left", expand=True)
        
        self.btn_settings = ctk.CTkButton(self.bottom_frame, text="", image=self.icon_settings, 
                                          width=40, fg_color="transparent", command=self.open_settings)
        self.btn_settings.pack(side="right", padx=20)
    
    def _load_audio_devices_thread(self):
        """Load audio devices using FFmpeg for correct names"""
        try:
            # 1. Get FFmpeg dshow names (Critical for recording stability)
            ffmpeg_names = self.recorder.handler.get_dshow_audio_names()
            
            # 2. Get PyAudio devices (For VU Meter)
            pyaudio_devices = self.audio_manager.get_input_devices()
            
            # 3. Update UI
            if ffmpeg_names:
                self.after(0, lambda: self._update_audio_ui(pyaudio_devices, ffmpeg_names))
            elif pyaudio_devices:
                 # Fallback if FFmpeg listing failed
                 names = [d['name'] for d in pyaudio_devices]
                 self.after(0, lambda: self._update_audio_ui(pyaudio_devices, names))
            else:
                 self.after(0, lambda: self._update_audio_ui([], []))
                 
        except Exception as e:
            self._logger.error(f"Audio device load error: {e}")

    def _update_audio_ui(self, devices, names):
        self.devices = devices  # PyAudio devices list
        self.device_names = names # Names to show in UI
        
        if names:
            self.device_combo.configure(values=names)
            self.device_combo.set(names[0])
            # Try to start monitoring for default device
            self._start_vu_monitoring(names[0])
        else:
            self.device_combo.configure(values=["No devices"])
            self.device_combo.set("No devices")
        
        self.update_vu_meter()

    def _start_vu_monitoring(self, selected_name):
        """Try to find corresponding PyAudio device and start monitoring"""
        try:
            # Try exact match first
            for dev in self.devices:
                if dev['name'] == selected_name:
                    self.audio_manager.start_monitoring(dev['index'])
                    return

            # Try partial match (FFmpeg name is usually shorter or cleaner)
            # e.g. FFmpeg: "Microphone (Realtek Audio)" vs PyAudio: "Microphone (Realtek Audio) (2- High Definition...)"
            for dev in self.devices:
                if selected_name in dev['name'] or dev['name'] in selected_name:
                    self.audio_manager.start_monitoring(dev['index'])
                    return
            
            # Try cleaning names (remove brackets content if needed, but simple partial is usually enough)
            
        except Exception:
            pass

    def set_mode(self, mode):
        self.recording_mode = mode
        self.window_combo.pack_forget()
        self.selected_rect = None
        
        default_color = "#1F6AA5"
        selected_color = NEON_BLUE
        
        self.btn_screen.configure(fg_color=selected_color if mode == "screen" else default_color)
        self.btn_region.configure(fg_color=selected_color if mode == "region" else default_color)
        self.btn_window.configure(fg_color=selected_color if mode == "window" else default_color)

    def select_region(self):
        self.set_mode("region")
        from gui.overlay import RegionOverlay
        overlay = RegionOverlay(self, self.on_region_selected)

    def on_region_selected(self, rect):
        self.selected_rect = rect

    def show_window_selector(self):
        self.set_mode("window")
        self.active_windows = self.window_finder.get_active_windows()
        titles = [w['title'] for w in self.active_windows]
        if titles:
            self.window_combo.configure(values=titles)
            self.window_combo.set(titles[0])
            self.window_combo.pack(pady=5, after=self.mode_frame)
            self.on_window_selected(titles[0])
        else:
            self.window_combo.configure(values=[self.t("no_windows")])
            self.window_combo.set(self.t("no_windows"))

    def on_window_selected(self, title):
        for w in self.active_windows:
            if w['title'] == title:
                self.selected_window_hwnd = w['hwnd']
                self.selected_rect = self.window_finder.get_window_rect(self.selected_window_hwnd)
                break

    def toggle_record(self):
        if not self.recorder.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.rec_btn.configure(image=self.icon_stop, fg_color="#333333")
        
        # Gather params immediately
        self.record_params = {
            "mic": self.device_combo.get() if self.mic_switch.get() else None,
            "system": self.sys_audio_switch.get()
        }
        
        # Stop audio monitoring (VU meter) to free up device for recording
        if hasattr(self, 'audio_manager'):
            self.audio_manager.stop_monitoring()
        
        self.withdraw()
        
        from gui.recording_widget import RecordingWidget
        self.widget = RecordingWidget(
            self, 
            on_stop=self.stop_recording, 
            on_pause=self.on_pause_recording,
            get_elapsed=self.recorder.get_elapsed_time,
            get_progress=self.recorder.get_progress
        )
        
        # Start recording in background thread to absolutely prevent freezing
        threading.Thread(target=self._start_recording_worker, daemon=True).start()
        
        # Start timer speculatively, it will correct itself
        self.update_timer()

    def _start_recording_worker(self):
        """Background worker to start ffmpeg process"""
        try:
            result = self.recorder.start(
                mode=self.recording_mode, 
                rect=self.selected_rect, 
                mic=self.record_params["mic"], 
                system=self.record_params["system"]
            )
            
            if not result:
                # Failed synchronously
                self.recorder.is_recording = False
                self.after(0, lambda: self.on_recording_error("Failed to start recording process"))
                
        except Exception as e:
            self.recorder.is_recording = False
            self.after(0, lambda: self.on_recording_error(f"Startup error: {e}"))

    def on_pause_recording(self, should_pause: bool) -> bool:
        if should_pause:
            success = self.recorder.pause()
            return success
        else:
            success = self.recorder.resume()
            return not success

    def stop_recording(self):
        if hasattr(self, 'widget') and self.widget:
            self.widget.destroy()
            self.widget = None
        
        result = self.recorder.stop()
        
        self.deiconify()
        self.rec_btn.configure(image=self.icon_rec, fg_color="transparent")
        self.timer_label.configure(text="00:00:00")
        
        # Results are shown
        if result:
            from utils.notifications import show_recording_complete
            filename = result.get("filename", "recording")
            duration = result.get("duration_formatted", "00:00")
            show_recording_complete(
                f"Recording saved: {filename}",
                f"Duration: {duration}"
            )
            
        # Restart audio monitoring if device selected
        if hasattr(self, 'audio_manager') and hasattr(self, 'devices'):
            current_name = self.device_combo.get()
            self._start_vu_monitoring(current_name)

    def update_timer(self):
        if self.recorder.is_recording:
            elapsed = int(self.recorder.get_elapsed_time())
            mins, secs = divmod(elapsed, 60)
            hrs, mins = divmod(mins, 60)
            self.timer_label.configure(text=f"{hrs:02d}:{mins:02d}:{secs:02d}")
            self.after(500, self.update_timer)

    def update_vu_meter(self):
        if hasattr(self, 'audio_manager') and hasattr(self, 'vu_meter'):
            level = self.audio_manager.get_vu_level()
            self.vu_meter.set_level(level)
            self.after(50, self.update_vu_meter)

    def open_folder(self):
        os.startfile(self.recorder.get_output_dir())

    def _open_quick_overlay(self):
        if self.quick_overlay:
            return
        from gui.quick_overlay import QuickOverlay
        self.quick_overlay = QuickOverlay(
            master=self,
            on_screenshot=self._quick_screenshot,
            on_record=self._quick_record,
            on_close=self._on_quick_overlay_closed
        )

    def _on_quick_overlay_closed(self):
        self.quick_overlay = None

    def _quick_screenshot(self, rect):
        try:
            path = self.screenshot_capture.capture_region(rect)
            if path:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB"
                from utils.notifications import show_simple_notification
                show_simple_notification(self.t("screenshot_saved"), f"{os.path.basename(path)} ({size_str})")
        except Exception as e:
            print(f"Screenshot error: {e}")

    def _quick_record(self, rect):
        self.selected_rect = rect
        self.recording_mode = "region"
        self.start_recording()

    def _minimize_to_tray(self):
        """Minimize to system tray"""
        if self.tray and self.tray.is_running:
            self.withdraw()
        else:
            self.iconify()
    
    def _show_from_tray(self):
        """Show window from tray"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self):
        self.on_closing(force_quit=True)

    def on_closing(self, force_quit=False):
        if not force_quit and self._settings.get("minimize_to_tray", True):
            if self.tray and self.tray.is_running:
                self._minimize_to_tray()
                return
        self._cleanup()
        self.destroy()
        import os
        os._exit(0)
    
    def _cleanup(self):
        self._settings.set("language", self.current_lang)
        self._settings.set("fps", self.current_fps)
        self._settings.set("quality", self.current_quality)
        self._settings.set("last_mode", self.recording_mode)
        
        if hasattr(self, 'recorder') and self.recorder and self.recorder.is_recording:
            self.recorder.stop()
        
        if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
            self.hotkey_manager.stop()
        
        if hasattr(self, 'tray') and self.tray:
            self.tray.stop()
        
        if hasattr(self, 'audio_manager') and self.audio_manager:
            self.audio_manager.stop_monitoring()
            self.audio_manager.terminate()
        
        if hasattr(self, 'screenshot_capture'):
            self.screenshot_capture.cleanup()
        
        if hasattr(self, 'widget') and self.widget:
            try:
                self.widget.destroy()
            except:
                pass
        
        if hasattr(self, 'quick_overlay') and self.quick_overlay:
            try:
                self.quick_overlay.destroy()
            except:
                pass


if __name__ == "__main__":
    app = NeoRecorderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
