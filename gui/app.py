
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
from core.studio.planner import SceneRecordingPlanner
from core.studio.session import StudioSessionService, TransitionKind
from core.studio.service import StudioProjectService
from gui.studio_presenter import (
    format_bounds,
    format_preview_caption,
    format_scene_summary,
    format_source_caption,
    format_source_kind,
)
from gui.widgets import MixerStrip, ScenePreview, VUMeter
from gui.overlay import RegionOverlay
from gui.recording_widget import RecordingWidget
from gui.tray import SystemTray
from gui.quick_overlay import QuickOverlay
from utils.display_manager import get_display_manager
from utils.notifications import show_error_notification, show_recording_complete, show_simple_notification
from utils.hotkeys import get_hotkey_manager
from utils.screenshot import get_screenshot_capture
from utils.logger import get_logger


STUDIO_BG = "#09131B"
STUDIO_SURFACE = "#101B27"
STUDIO_PANEL = "#162433"
STUDIO_PANEL_ALT = "#1B2D3F"
STUDIO_BORDER = "#274459"
STUDIO_TEXT = "#F4FBFF"
STUDIO_MUTED = "#86A2B6"
STUDIO_ACCENT = "#27C1F4"
STUDIO_WARN = "#F26D3D"
STUDIO_GO = "#1FA971"

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(parent.t("settings"))
        self.geometry("480x650")
        self.configure(fg_color=STUDIO_BG)
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
        lang_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
        lang_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(lang_frame, text="Language / Язык:", 
                    font=("Segoe UI", 12, "bold")).pack(pady=10, padx=15, anchor="w")
        self.lang_combo = ctk.CTkComboBox(lang_frame, values=["ru", "en"], 
                                          width=200, command=self.change_lang)
        self.lang_combo.set(self.parent.current_lang)
        self.lang_combo.pack(pady=(0, 12), padx=15, anchor="w")

        # === Recording Settings ===
        rec_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        path_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        tray_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        hotkey_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        scr_path_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        ovr_frame = ctk.CTkFrame(self.scroll_frame, fg_color=STUDIO_PANEL, corner_radius=12)
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
        save_btn = ctk.CTkButton(
            self,
            text="Сохранить",
            width=140,
            height=40,
            fg_color=ACCENT_COLOR,
            hover_color="#46D0FF",
            text_color=STUDIO_TEXT,
            command=self.save_and_close,
        )
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
        self.geometry("1480x860")
        self.configure(fg_color=STUDIO_BG)
        
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
        ctk.CTkLabel(self.loading_frame, text="NeoRecorder", font=("Bahnschrift SemiCondensed", 34, "bold"), text_color=NEON_BLUE).pack(pady=10)
        ctk.CTkLabel(self.loading_frame, text="Loading Studio Workspace...", font=("Consolas", 14), text_color=SECONDARY_TEXT_COLOR).pack()
        
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
        self.display_manager = get_display_manager()
        self.displays = self.display_manager.list_monitors()
        self.hotkey_manager = get_hotkey_manager()
        self.project_service = StudioProjectService()
        self.session_service = StudioSessionService()
        self.recording_planner = SceneRecordingPlanner()
        self.project = self.project_service.create_project("NeoRecorder Session")
        self.studio_session = self.session_service.create_session(self.project)
        
        # Register recorder callbacks
        self.recorder.set_callbacks(
            on_error=self.on_recording_error,
            on_complete=self.on_recording_complete_event
        )
        
        # State
        self.recording_mode = self._settings.get("last_mode", "screen")
        self.selected_rect = None
        self.selected_window_hwnd = None
        self.selected_display_index = 1
        self.active_windows = []
        self.selected_scene_id = self.studio_session.preview_scene_id
        self.selected_source_id = None
        self.widget = None
        self.quick_overlay = None
        self.tray = None

    def on_recording_error(self, error):
        """Handle recording error from backend"""
        self.after(0, lambda: self._handle_recording_error_ui(error))
        
    def _handle_recording_error_ui(self, error):
        # Stop UI state
        if hasattr(self, 'widget') and self.widget:
            self.widget.destroy()
            self.widget = None
        
        self.deiconify()
        self.rec_btn.configure(image=self.icon_rec, fg_color="#203345", hover_color="#28465E")
        self.timer_label.configure(text="00:00:00")
        self._refresh_dashboard()
        
        show_error_notification("Recording Error", str(error))
        
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
        self._load_icons()
        self._build_studio_shell()
        self._bootstrap_dashboard_state()
        threading.Thread(target=self._load_audio_devices_thread, daemon=True).start()

    def _load_icons(self):
        self.icon_rec = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "rec.png")), size=(72, 72))
        self.icon_stop = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "stop.png")), size=(72, 72))
        self.icon_folder = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "folder.png")), size=(22, 22))
        self.icon_settings = ctk.CTkImage(Image.open(os.path.join(ICONS_DIR, "settings.png")), size=(22, 22))

    def _build_studio_shell(self):
        self.configure(fg_color=STUDIO_BG)
        self.shell = ctk.CTkFrame(self, fg_color=STUDIO_BG)
        self.shell.pack(fill="both", expand=True, padx=18, pady=18)
        self._build_header_bar()
        self._build_workspace()
        self._build_footer_bar()

    def _build_header_bar(self):
        self.header_bar = ctk.CTkFrame(self.shell, fg_color=STUDIO_SURFACE, corner_radius=24)
        self.header_bar.pack(fill="x", pady=(0, 16))

        identity = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        identity.pack(side="left", padx=20, pady=18)
        ctk.CTkLabel(
            identity,
            text="NeoRecorder Studio",
            font=("Bahnschrift SemiCondensed", 30, "bold"),
            text_color=STUDIO_TEXT,
        ).pack(anchor="w")
        self.header_subtitle = ctk.CTkLabel(
            identity,
            text="Scene deck, live preview and capture mixer",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.header_subtitle.pack(anchor="w", pady=(2, 0))

        status_wrap = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        status_wrap.pack(side="left", padx=12)
        self.session_status_label = self._create_pill(status_wrap, "READY", STUDIO_GO)
        self.session_scene_label = self._create_pill(status_wrap, "SCENE 01", "#37506A")

        controls = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        controls.pack(side="right", padx=20, pady=14)
        self.timer_label = ctk.CTkLabel(
            controls,
            text="00:00:00",
            font=("Consolas", 22, "bold"),
            text_color=STUDIO_TEXT,
            width=128,
        )
        self.timer_label.pack(side="left", padx=(0, 14))
        self.btn_folder = self._create_icon_button(controls, self.icon_folder, self.open_folder)
        self.btn_folder.pack(side="left", padx=6)
        self.btn_settings = self._create_icon_button(controls, self.icon_settings, self.open_settings)
        self.btn_settings.pack(side="left", padx=6)
        self.rec_btn = ctk.CTkButton(
            controls,
            text="",
            image=self.icon_rec,
            width=86,
            height=86,
            corner_radius=43,
            fg_color="#203345",
            hover_color="#28465E",
            command=self.toggle_record,
        )
        self.rec_btn.pack(side="left", padx=(10, 0))

    def _build_workspace(self):
        self.workspace = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.workspace.pack(fill="both", expand=True)
        self.workspace.grid_columnconfigure(1, weight=1)
        self.workspace.grid_rowconfigure(0, weight=1)

        self._build_left_column()
        self._build_center_column()
        self._build_right_column()

    def _build_left_column(self):
        self.left_column = ctk.CTkFrame(self.workspace, fg_color="transparent", width=300)
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._build_scene_panel()
        self._build_source_panel()

    def _build_center_column(self):
        self.center_column = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.center_column.grid(row=0, column=1, sticky="nsew")
        self.center_column.grid_rowconfigure(0, weight=1)
        self.center_column.grid_columnconfigure(0, weight=1)
        self._build_preview_panel()
        self._build_transport_panel()

    def _build_right_column(self):
        self.right_column = ctk.CTkFrame(self.workspace, fg_color="transparent", width=340)
        self.right_column.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        self._build_audio_panel()
        self._build_inspector_panel()

    def _build_scene_panel(self):
        self.scene_panel = ctk.CTkFrame(self.left_column, fg_color=STUDIO_PANEL, corner_radius=22)
        self.scene_panel.pack(fill="x", pady=(0, 12))
        self._create_panel_title(self.scene_panel, "SCENES", self._add_scene)
        self.scene_list = ctk.CTkScrollableFrame(self.scene_panel, fg_color="transparent", height=240)
        self.scene_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_source_panel(self):
        self.source_panel = ctk.CTkFrame(self.left_column, fg_color=STUDIO_PANEL, corner_radius=22)
        self.source_panel.pack(fill="both", expand=True)
        self._create_panel_title(self.source_panel, "SOURCES", None)
        source_tools = ctk.CTkFrame(self.source_panel, fg_color="transparent")
        source_tools.pack(fill="x", padx=12, pady=(0, 8))
        self._create_mode_button(source_tools, self.t("mode_screen"), lambda: self.set_mode("screen")).pack(
            side="left", padx=(0, 6)
        )
        self._create_mode_button(source_tools, self.t("mode_region"), self.select_region).pack(side="left", padx=6)
        self._create_mode_button(source_tools, self.t("mode_window"), self.show_window_selector).pack(side="left", padx=6)
        self.source_list = ctk.CTkScrollableFrame(self.source_panel, fg_color="transparent")
        self.source_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_preview_panel(self):
        self.preview_panel = ctk.CTkFrame(self.center_column, fg_color=STUDIO_SURFACE, corner_radius=24)
        self.preview_panel.grid(row=0, column=0, sticky="nsew")
        preview_header = ctk.CTkFrame(self.preview_panel, fg_color="transparent")
        preview_header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            preview_header,
            text="STUDIO MODE",
            font=("Bahnschrift", 18, "bold"),
            text_color=STUDIO_TEXT,
        ).pack(side="left")
        self.preview_caption_label = ctk.CTkLabel(
            preview_header,
            text="0 layers",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.preview_caption_label.pack(side="right")

        stage = ctk.CTkFrame(self.preview_panel, fg_color="transparent")
        stage.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        stage.grid_columnconfigure(0, weight=1)
        stage.grid_columnconfigure(1, weight=1)

        preview_frame = ctk.CTkFrame(stage, fg_color=STUDIO_PANEL_ALT, corner_radius=20)
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(preview_frame, text="PREVIEW", font=("Bahnschrift", 15, "bold"), text_color=STUDIO_TEXT).pack(anchor="w", padx=14, pady=(12, 6))
        self.preview_scene_label = ctk.CTkLabel(preview_frame, text="", font=("Consolas", 11), text_color=STUDIO_MUTED)
        self.preview_scene_label.pack(anchor="w", padx=14, pady=(0, 6))
        self.preview_widget = ScenePreview(preview_frame, width=320, height=250)
        self.preview_widget.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        program_frame = ctk.CTkFrame(stage, fg_color=STUDIO_PANEL_ALT, corner_radius=20)
        program_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(program_frame, text="PROGRAM", font=("Bahnschrift", 15, "bold"), text_color=STUDIO_TEXT).pack(anchor="w", padx=14, pady=(12, 6))
        self.program_scene_label = ctk.CTkLabel(program_frame, text="", font=("Consolas", 11), text_color=STUDIO_MUTED)
        self.program_scene_label.pack(anchor="w", padx=14, pady=(0, 6))
        self.program_widget = ScenePreview(program_frame, width=320, height=250)
        self.program_widget.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_transport_panel(self):
        self.transport_panel = ctk.CTkFrame(self.center_column, fg_color=STUDIO_PANEL_ALT, corner_radius=22)
        self.transport_panel.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        mode_row = ctk.CTkFrame(self.transport_panel, fg_color="transparent")
        mode_row.pack(fill="x", padx=16, pady=(16, 10))
        self.btn_screen = self._create_mode_button(mode_row, self.t("mode_screen"), lambda: self.set_mode("screen"))
        self.btn_screen.pack(side="left", padx=(0, 8))
        self.btn_region = self._create_mode_button(mode_row, self.t("mode_region"), self.select_region)
        self.btn_region.pack(side="left", padx=8)
        self.btn_window = self._create_mode_button(mode_row, self.t("mode_window"), self.show_window_selector)
        self.btn_window.pack(side="left", padx=8)

        picker_row = ctk.CTkFrame(self.transport_panel, fg_color="transparent")
        picker_row.pack(fill="x", padx=16, pady=(0, 16))
        self.display_combo = ctk.CTkComboBox(
            picker_row,
            values=["Display 1"],
            width=280,
            command=self._on_display_selected,
        )
        self.display_combo.pack(side="left", padx=(0, 12))
        self.window_combo = ctk.CTkComboBox(
            picker_row,
            values=[self.t("select_window")],
            width=260,
            command=self.on_window_selected,
        )
        self.window_combo.pack(side="left")
        self.window_combo.set(self.t("select_window"))
        self.preview_mode_label = ctk.CTkLabel(
            picker_row,
            text="",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.preview_mode_label.pack(side="right")

        transition_row = ctk.CTkFrame(self.transport_panel, fg_color="transparent")
        transition_row.pack(fill="x", padx=16, pady=(0, 16))
        self.transition_combo = ctk.CTkComboBox(
            transition_row,
            values=["CUT", "FADE", "SLIDE"],
            width=150,
            command=self._on_transition_changed,
        )
        self.transition_combo.pack(side="left")
        self.transition_combo.set("CUT")
        self.take_button = ctk.CTkButton(
            transition_row,
            text="TAKE",
            width=120,
            height=38,
            corner_radius=14,
            fg_color=STUDIO_WARN,
            hover_color="#FF8A57",
            text_color=STUDIO_TEXT,
            command=self._take_preview_to_program,
        )
        self.take_button.pack(side="left", padx=12)
        self.take_status_label = ctk.CTkLabel(
            transition_row,
            text="Preview matches program",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.take_status_label.pack(side="left", padx=8)

    def _build_audio_panel(self):
        self.audio_panel = ctk.CTkFrame(self.right_column, fg_color=STUDIO_PANEL, corner_radius=22)
        self.audio_panel.pack(fill="x", pady=(0, 12))
        self._create_panel_title(self.audio_panel, "AUDIO MIXER", None)

        control_row = ctk.CTkFrame(self.audio_panel, fg_color="transparent")
        control_row.pack(fill="x", padx=14, pady=(0, 10))
        self.mic_switch = ctk.CTkSwitch(
            control_row,
            text=self.t("mic_source"),
            progress_color=STUDIO_ACCENT,
            command=self._on_audio_settings_changed,
        )
        self.mic_switch.pack(anchor="w")
        self.sys_audio_switch = ctk.CTkSwitch(
            control_row,
            text=self.t("system_source"),
            progress_color=STUDIO_ACCENT,
            command=self._on_audio_settings_changed,
        )
        self.sys_audio_switch.pack(anchor="w", pady=(8, 0))

        self.device_combo = ctk.CTkComboBox(
            self.audio_panel,
            values=[self.t("loading")],
            command=self._on_audio_settings_changed,
        )
        self.device_combo.pack(fill="x", padx=14)
        self.device_combo.set(self.t("loading"))
        self.vu_meter = VUMeter(self.audio_panel, width=290, height=10)
        self.vu_meter.pack(fill="x", padx=14, pady=12)
        self.mixer_list = ctk.CTkScrollableFrame(self.audio_panel, fg_color="transparent", height=220)
        self.mixer_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_inspector_panel(self):
        self.inspector_panel = ctk.CTkFrame(self.right_column, fg_color=STUDIO_PANEL, corner_radius=22)
        self.inspector_panel.pack(fill="both", expand=True)
        self._create_panel_title(self.inspector_panel, "INSPECTOR", None)
        self.inspector_body = ctk.CTkFrame(self.inspector_panel, fg_color="transparent")
        self.inspector_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _build_footer_bar(self):
        self.footer_bar = ctk.CTkFrame(self.shell, fg_color=STUDIO_SURFACE, corner_radius=20)
        self.footer_bar.pack(fill="x", pady=(16, 0))
        self.fps_label = ctk.CTkLabel(
            self.footer_bar,
            text="",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.fps_label.pack(side="left", padx=18, pady=12)
        self.output_label = ctk.CTkLabel(
            self.footer_bar,
            text="",
            font=("Consolas", 11),
            text_color=STUDIO_MUTED,
        )
        self.output_label.pack(side="right", padx=18, pady=12)

    def _bootstrap_dashboard_state(self):
        if self.recording_mode == "region" and not self.selected_rect:
            self.recording_mode = "screen"
        self._refresh_display_options()
        self.transition_combo.set(self.studio_session.transition.kind.value.upper())
        self._ensure_active_scene_video_source()
        self._sync_controls_from_scene()
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def _ensure_active_scene_video_source(self):
        scene = self._active_scene()
        if scene.video_sources():
            return
        self._sync_active_scene_video_source()

    def _sync_controls_from_scene(self):
        scene = self._active_scene()
        primary = scene.primary_video_source()
        if primary is None:
            return
        self.recording_mode = self._mode_from_source(primary)
        self.selected_rect = None if primary.kind.value == "display_capture" else primary.bounds.to_rect() if primary.bounds else None
        self.selected_window_hwnd = primary.metadata.get("hwnd") if primary.kind.value == "window_capture" else None
        self.selected_display_index = primary.display_index() or self.selected_display_index
        self.selected_source_id = self.selected_source_id or primary.source_id
        self._sync_display_combo()
        self._sync_audio_controls(scene)

    def _sync_audio_controls(self, scene):
        mic_source = next((source for source in scene.audio_sources() if source.kind.value == "microphone_input"), None)
        system_source = next((source for source in scene.audio_sources() if source.kind.value == "system_audio"), None)
        self._set_switch_state(self.mic_switch, mic_source is not None and mic_source.enabled)
        self._set_switch_state(self.sys_audio_switch, system_source is not None and system_source.enabled)
        if mic_source and mic_source.target:
            self.device_combo.set(mic_source.target)

    def _set_switch_state(self, widget, enabled):
        if enabled:
            widget.select()
            return
        widget.deselect()

    def _active_scene(self):
        return self.project.get_scene(self.selected_scene_id) or self._program_scene()

    def _program_scene(self):
        return self.project.get_scene(self.studio_session.program_scene_id) or self.project.active_scene()

    def _refresh_display_options(self):
        self.displays = self.display_manager.list_monitors()
        labels = [monitor.to_label() for monitor in self.displays]
        self._display_labels = {label: monitor.index for label, monitor in zip(labels, self.displays)}
        self.display_combo.configure(values=labels or ["Display 1"])
        self._sync_display_combo()

    def _sync_display_combo(self):
        if not getattr(self, "_display_labels", None):
            return
        for label, index in self._display_labels.items():
            if index == self.selected_display_index:
                self.display_combo.set(label)
                return
        first_label = next(iter(self._display_labels))
        self.display_combo.set(first_label)
        self.selected_display_index = self._display_labels[first_label]

    def _selected_display_monitor(self):
        return self.display_manager.get_monitor(self.selected_display_index)

    def _on_display_selected(self, label):
        self.selected_display_index = self._display_labels.get(label, 1)
        self.recording_mode = "screen"
        self.selected_rect = None
        self._sync_active_scene_video_source()
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def _on_transition_changed(self, label):
        mapping = {
            "CUT": TransitionKind.CUT,
            "FADE": TransitionKind.FADE,
            "SLIDE": TransitionKind.SLIDE,
        }
        self.studio_session = self.session_service.set_transition(
            self.studio_session,
            mapping.get(label, TransitionKind.CUT),
        )
        self._refresh_dashboard()

    def _take_preview_to_program(self):
        self.project, self.studio_session = self.session_service.take(self.project, self.studio_session)
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        preview_scene = self._active_scene()
        program_scene = self._program_scene()
        self._ensure_selected_source(preview_scene)
        self._refresh_status_bar(preview_scene, program_scene)
        self._render_scene_list()
        self._render_source_list(preview_scene)
        self._render_mixer(preview_scene)
        self._render_inspector(preview_scene)
        self.preview_widget.render(preview_scene)
        self.program_widget.render(program_scene)
        self.preview_scene_label.configure(text=preview_scene.name)
        self.program_scene_label.configure(text=program_scene.name)
        self.preview_caption_label.configure(
            text=f"{format_preview_caption(preview_scene)} • {self.studio_session.transition.kind.value.upper()}",
        )

    def _ensure_selected_source(self, scene):
        if self.selected_source_id and scene.get_source(self.selected_source_id):
            return
        primary = scene.primary_video_source()
        if primary:
            self.selected_source_id = primary.source_id
            return
        self.selected_source_id = scene.sources[0].source_id if scene.sources else None

    def _refresh_status_bar(self, preview_scene, program_scene):
        encoder = self.recorder.get_best_encoder()
        encoder_short = "NVENC" if "nvenc" in encoder else "QSV" if "qsv" in encoder else "AMF" if "amf" in encoder else "CPU"
        state_text = "REC" if self.recorder.is_recording else "READY"
        state_color = STUDIO_WARN if self.recorder.is_recording else STUDIO_GO
        display_name = self._selected_display_monitor().name if self.recording_mode == "screen" else self.recording_mode.upper()
        self.session_status_label.configure(text=state_text, fg_color=state_color)
        self.session_scene_label.configure(text=program_scene.name.upper(), fg_color="#28445B")
        self.header_subtitle.configure(text=f"Preview: {preview_scene.name} • Program: {program_scene.name}")
        transition_name = self.studio_session.transition.kind.value.upper()
        self.preview_mode_label.configure(text=f"{display_name.upper()} • {transition_name} • {encoder_short} • {self.current_fps} FPS")
        self.fps_label.configure(text=f"{self.current_fps} FPS • {self.current_quality.upper()} • {encoder_short}")
        self.output_label.configure(text=self.recorder.get_output_dir())
        take_text = "Preview matches program" if preview_scene.scene_id == program_scene.scene_id else f"Ready to TAKE via {transition_name}"
        self.take_status_label.configure(text=take_text)

    def _render_scene_list(self):
        self._clear_frame(self.scene_list)
        for scene in self.project.scenes:
            self._create_scene_card(scene).pack(fill="x", pady=6)

    def _render_source_list(self, scene):
        self._clear_frame(self.source_list)
        for source in scene.ordered_sources():
            self._create_source_row(source).pack(fill="x", pady=6)

    def _render_mixer(self, scene):
        self._clear_frame(self.mixer_list)
        channels = scene.audio_sources()
        if not channels:
            self._create_empty_label(self.mixer_list, "No audio channels in this scene").pack(fill="x", pady=10)
            return
        for source in channels:
            strip = MixerStrip(self.mixer_list, source, self._update_source_volume, self._toggle_source_mute)
            strip.pack(fill="x", pady=6)

    def _render_inspector(self, scene):
        self._clear_frame(self.inspector_body)
        source = scene.get_source(self.selected_source_id) if self.selected_source_id else None
        if source is None:
            self._create_empty_label(self.inspector_body, "Select a source to inspect").pack(fill="x", pady=14)
            return

        self._create_inspector_value("Name", source.name).pack(fill="x", pady=6)
        self._create_inspector_value("Type", format_source_kind(source.kind)).pack(fill="x", pady=6)
        self._create_inspector_value("Placement", format_bounds(source.bounds)).pack(fill="x", pady=6)
        self._create_inspector_value("State", format_source_caption(source)).pack(fill="x", pady=6)
        if source.is_audio():
            self._create_inspector_slider("Volume", source.volume, self._update_source_volume, source.source_id).pack(
                fill="x", pady=(16, 8)
            )
        if source.is_video():
            self._create_inspector_slider("Opacity", source.opacity, self._update_source_opacity, source.source_id).pack(
                fill="x", pady=(16, 8)
            )

    def _create_scene_card(self, scene):
        is_active = scene.scene_id == self.selected_scene_id
        is_program = scene.scene_id == self.studio_session.program_scene_id
        state_label = (
            "PREVIEW / PROGRAM"
            if is_active and is_program
            else "PREVIEW"
            if is_active
            else "PROGRAM"
            if is_program
            else "SCENE"
        )
        card = ctk.CTkButton(
            self.scene_list,
            text=f"{scene.name}\n{state_label} • {format_scene_summary(scene)}",
            anchor="w",
            height=64,
            corner_radius=16,
            fg_color=STUDIO_ACCENT if is_active else "#8E4A33" if is_program else STUDIO_PANEL_ALT,
            hover_color="#1D5F7A" if is_active else "#B56042" if is_program else "#24384C",
            text_color=STUDIO_TEXT,
            command=lambda sid=scene.scene_id: self._select_scene(sid),
        )
        return card

    def _create_source_row(self, source):
        row = ctk.CTkFrame(self.source_list, fg_color=STUDIO_PANEL_ALT, corner_radius=16)
        main = ctk.CTkButton(
            row,
            text=f"{source.name}\n{format_source_caption(source)}",
            anchor="w",
            height=56,
            fg_color="transparent",
            hover_color="#22384A",
            text_color=STUDIO_TEXT,
            command=lambda sid=source.source_id: self._select_source(sid),
        )
        main.pack(side="left", fill="x", expand=True, padx=(4, 6), pady=4)
        self._create_action_button(row, "ON" if source.enabled else "OFF", lambda sid=source.source_id: self._toggle_source_enabled(sid)).pack(side="left", padx=4)
        action_text = "MUTE" if source.is_audio() else "TOP"
        action_command = lambda sid=source.source_id: self._toggle_source_mute(sid, not source.muted) if source.is_audio() else self._move_source_to_top(sid)
        self._create_action_button(row, action_text, action_command).pack(side="left", padx=(0, 6))
        return row

    def _create_panel_title(self, master, title, action):
        header = ctk.CTkFrame(master, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(14, 10))
        ctk.CTkLabel(header, text=title, font=("Bahnschrift", 18, "bold"), text_color=STUDIO_TEXT).pack(side="left")
        if action:
            self._create_action_button(header, "ADD", action).pack(side="right")

    def _create_pill(self, master, text, color):
        label = ctk.CTkLabel(
            master,
            text=f"  {text}  ",
            fg_color=color,
            corner_radius=999,
            text_color=STUDIO_TEXT,
            font=("Consolas", 11, "bold"),
        )
        label.pack(side="left", padx=6)
        return label

    def _create_icon_button(self, master, image, command):
        return ctk.CTkButton(
            master,
            text="",
            image=image,
            width=42,
            height=42,
            corner_radius=14,
            fg_color=STUDIO_PANEL,
            hover_color="#213446",
            command=command,
        )

    def _create_mode_button(self, master, text, command):
        return ctk.CTkButton(
            master,
            text=text,
            height=38,
            corner_radius=14,
            fg_color=STUDIO_PANEL,
            hover_color="#274559",
            text_color=STUDIO_TEXT,
            command=command,
        )

    def _create_action_button(self, master, text, command):
        return ctk.CTkButton(
            master,
            text=text,
            width=58,
            height=30,
            corner_radius=12,
            fg_color="#243A4D",
            hover_color="#31516B",
            text_color=STUDIO_TEXT,
            font=("Consolas", 10, "bold"),
            command=command,
        )

    def _create_empty_label(self, master, text):
        return ctk.CTkLabel(master, text=text, text_color=STUDIO_MUTED, font=("Consolas", 11))

    def _create_inspector_value(self, label, value):
        frame = ctk.CTkFrame(self.inspector_body, fg_color=STUDIO_PANEL_ALT, corner_radius=14)
        ctk.CTkLabel(frame, text=label.upper(), text_color=STUDIO_MUTED, font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(frame, text=value, text_color=STUDIO_TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(0, 10))
        return frame

    def _create_inspector_slider(self, label, value, callback, source_id):
        frame = ctk.CTkFrame(self.inspector_body, fg_color=STUDIO_PANEL_ALT, corner_radius=14)
        ctk.CTkLabel(frame, text=label.upper(), text_color=STUDIO_MUTED, font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 8))
        slider = ctk.CTkSlider(frame, from_=0, to=1, number_of_steps=20, progress_color=STUDIO_ACCENT, command=lambda raw: callback(source_id, float(raw)))
        slider.pack(fill="x", padx=12, pady=(0, 10))
        slider.set(value)
        return frame

    def _clear_frame(self, frame):
        for child in frame.winfo_children():
            child.destroy()
    
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
        else:
            self.device_combo.configure(values=["No devices"])
            self.device_combo.set("No devices")
        
        self._on_audio_settings_changed()
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

    def _select_scene(self, scene_id):
        self.selected_scene_id = scene_id
        self.studio_session = self.session_service.set_preview_scene(self.project, self.studio_session, scene_id)
        self.selected_source_id = None
        self._sync_controls_from_scene()
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def _add_scene(self):
        name = f"Scene {len(self.project.scenes) + 1}"
        self.project = self.project_service.add_scene(self.project, name)
        self.selected_scene_id = self.project.scenes[-1].scene_id
        self.studio_session = self.session_service.set_preview_scene(self.project, self.studio_session, self.selected_scene_id)
        self._sync_active_scene_video_source()
        self._refresh_dashboard()

    def _select_source(self, source_id):
        self.selected_source_id = source_id
        self._refresh_dashboard()

    def _toggle_source_enabled(self, source_id):
        scene = self._active_scene()
        source = scene.get_source(source_id)
        if source is None:
            return
        self.project = self.project_service.enable_source(
            self.project,
            scene.scene_id,
            source_id,
            not source.enabled,
        )
        self._refresh_dashboard()

    def _toggle_source_mute(self, source_id, muted):
        self.project = self.project_service.mute_source(self.project, self._active_scene().scene_id, source_id, muted)
        self._refresh_dashboard()

    def _move_source_to_top(self, source_id):
        max_z = max((source.z_index for source in self._active_scene().sources), default=0)
        self.project = self.project_service.reorder_source(
            self.project,
            self._active_scene().scene_id,
            source_id,
            max_z + 1,
        )
        self._refresh_dashboard()

    def _update_source_volume(self, source_id, volume):
        self.project = self.project_service.set_source_volume(
            self.project,
            self._active_scene().scene_id,
            source_id,
            volume,
        )
        self._refresh_dashboard()

    def _update_source_opacity(self, source_id, opacity):
        self.project = self.project_service.set_source_opacity(
            self.project,
            self._active_scene().scene_id,
            source_id,
            opacity,
        )
        self._refresh_dashboard()

    def _on_audio_settings_changed(self, _value=None):
        current_name = self.device_combo.get()
        if self.mic_switch.get() and current_name not in {"", self.t("loading"), "No devices"}:
            self._start_vu_monitoring(current_name)
        else:
            self.audio_manager.stop_monitoring()
        self._sync_audio_sources()
        self._refresh_dashboard()

    def set_mode(self, mode):
        self.recording_mode = mode
        self.selected_rect = None if mode == "screen" else self.selected_rect
        self._sync_active_scene_video_source()
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def _apply_mode_visuals(self):
        selected = STUDIO_ACCENT
        idle = STUDIO_PANEL
        self.btn_screen.configure(fg_color=selected if self.recording_mode == "screen" else idle)
        self.btn_region.configure(fg_color=selected if self.recording_mode == "region" else idle)
        self.btn_window.configure(fg_color=selected if self.recording_mode == "window" else idle)

    def select_region(self):
        self.recording_mode = "region"
        from gui.overlay import RegionOverlay
        RegionOverlay(self, self.on_region_selected)

    def on_region_selected(self, rect):
        self.selected_rect = rect
        self._sync_active_scene_video_source()
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def show_window_selector(self):
        self.recording_mode = "window"
        self.active_windows = self.window_finder.get_active_windows()
        titles = [w['title'] for w in self.active_windows]
        if titles:
            self.window_combo.configure(values=titles)
            self.window_combo.set(titles[0])
            self.on_window_selected(titles[0])
        else:
            self.window_combo.configure(values=[self.t("no_windows")])
            self.window_combo.set(self.t("no_windows"))
        self._apply_mode_visuals()
        self._refresh_dashboard()

    def on_window_selected(self, title):
        for w in self.active_windows:
            if w['title'] == title:
                self.selected_window_hwnd = w['hwnd']
                self.selected_rect = self.window_finder.get_window_rect(self.selected_window_hwnd)
                self._sync_active_scene_video_source()
                self._refresh_dashboard()
                break

    def toggle_record(self):
        if not self.recorder.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.rec_btn.configure(image=self.icon_stop, fg_color="#67293A", hover_color="#803145")
        
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
        self._refresh_dashboard()

    def _start_recording_worker(self):
        """Background worker to start ffmpeg process"""
        try:
            request = self._create_recording_request()
            result = self.recorder.start_request(request)
            
            if not result:
                # Failed synchronously
                self.recorder.is_recording = False
                self.after(0, lambda: self.on_recording_error("Failed to start recording process"))
                
        except Exception as e:
            self.recorder.is_recording = False
            self.after(0, lambda: self.on_recording_error(f"Startup error: {e}"))

    def _create_recording_request(self):
        self._sync_active_scene_video_source()
        self._sync_audio_sources()
        return self.recording_planner.build_request(self._program_scene())

    def _selected_window_title(self) -> str:
        if self.recording_mode != "window":
            return ""
        if not hasattr(self, "window_combo"):
            return ""
        return self.window_combo.get()

    def _sync_active_scene_video_source(self):
        scene = self._active_scene()
        primary = self._source_from_mode(scene)
        overlays = list(scene.overlay_video_sources())
        audio_sources = [source for source in scene.sources if source.is_audio()]
        self.project = self.project_service.replace_sources(
            self.project,
            scene.scene_id,
            [primary, *overlays, *audio_sources],
        )
        self.selected_source_id = primary.source_id

    def _source_from_mode(self, scene):
        if self.recording_mode == "screen":
            existing = scene.primary_video_source()
            monitor = self._selected_display_monitor()
            name = existing.display_name() if existing and existing.kind.value == "display_capture" else monitor.name
            return self.project_service.create_display_source(
                name=name,
                monitor_index=monitor.index,
                monitor_name=monitor.name,
                bounds=monitor.bounds.to_rect(),
            )
        if self.recording_mode == "window":
            return self.project_service.create_window_source(
                self._selected_window_title() or "Window Capture",
                self.selected_window_hwnd,
                self.selected_rect,
            )
        rect = self.selected_rect or (0, 0, 1280, 720)
        return self.project_service.create_region_source(rect)

    def _sync_audio_sources(self):
        scene = self._active_scene()
        sources = [source for source in scene.sources if not source.is_audio()]
        mic_source = self._preserve_audio_source(scene, "microphone_input")
        system_source = self._preserve_audio_source(scene, "system_audio")
        if mic_source:
            sources.append(mic_source)
        if system_source:
            sources.append(system_source)
        self.project = self.project_service.replace_sources(self.project, scene.scene_id, sources)

    def _preserve_audio_source(self, scene, kind):
        current = next((source for source in scene.sources if source.kind.value == kind), None)
        if kind == "microphone_input":
            device_name = self.device_combo.get()
            if not self.mic_switch.get() or device_name in {"", self.t("loading"), "No devices"}:
                return None
            base = current if current and current.target == device_name else self.project_service.create_microphone_source(device_name)
            return base.with_volume(current.volume if current else 1.0).with_muted(current.muted if current else False)
        if not self.sys_audio_switch.get():
            return None
        base = current or self.project_service.create_system_audio_source()
        return base.with_volume(current.volume if current else 1.0).with_muted(current.muted if current else False)

    def _mode_from_source(self, source):
        if source.kind.value == "display_capture":
            return "screen"
        if source.kind.value == "window_capture":
            return "window"
        return "region"

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
        self.rec_btn.configure(image=self.icon_rec, fg_color="#203345", hover_color="#28465E")
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
        self._refresh_dashboard()

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
        self._sync_active_scene_video_source()
        self._apply_mode_visuals()
        self._refresh_dashboard()
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
