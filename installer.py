
import customtkinter as ctk
import os
import shutil
import zipfile
import winreg
import sys
from PIL import Image

class NeoInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NeoRecorder - Installer")
        self.geometry("500x400")
        self.configure(fg_color="#2B2B2B")
        
        self.install_path = os.path.join(os.environ["ProgramFiles"], "NeoRecorder")
        self.source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "NeoRecorder")
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        self.header = ctk.CTkLabel(self, text="NeoRecorder Installation", font=("Segoe UI", 24, "bold"), text_color="#00F2FF")
        self.header.pack(pady=30)

        # Path Selection
        self.path_label = ctk.CTkLabel(self, text="Select Installation Folder:", font=("Segoe UI", 12))
        self.path_label.pack(pady=(10, 0), padx=40, anchor="w")
        
        self.path_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.path_frame.pack(pady=5, padx=40, fill="x")
        
        self.path_entry = ctk.CTkEntry(self.path_frame, width=300)
        self.path_entry.insert(0, self.install_path)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_btn = ctk.CTkButton(self.path_frame, text="Browse", width=80, command=self.browse_path)
        self.browse_btn.pack(side="right")

        # Progress
        self.progress = ctk.CTkProgressBar(self, width=400, progress_color="#00F2FF")
        self.progress.set(0)
        self.progress.pack(pady=40)
        
        self.status_label = ctk.CTkLabel(self, text="Ready to install", font=("Segoe UI", 10))
        self.status_label.pack()

        # Install Button
        self.install_btn = ctk.CTkButton(self, text="INSTALL NOW", font=("Segoe UI", 16, "bold"), 
                                         fg_color="#1F6AA5", hover_color="#144e7a",
                                         width=200, height=50, command=self.run_installation)
        self.install_btn.pack(pady=20)

    def browse_path(self):
        new_path = ctk.filedialog.askdirectory(initialdir=self.install_path)
        if new_path:
            self.install_path = new_path
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, self.install_path)

    def run_installation(self):
        self.install_path = self.path_entry.get()
        self.install_btn.configure(state="disabled")
        self.status_label.configure(text="Installing...")
        
        try:
            if not os.path.exists(self.source_dir):
                 # For the sake of demonstration, we assume dist/NeoRecorder exists
                 # In a real scenario, we might use a ZIP embedded in the installer
                 pass

            # Update progress simulated for UI
            self.progress.set(0.3)
            self.update_idletasks()
            
            # Copy files
            if os.path.exists(self.install_path):
                shutil.rmtree(self.install_path, ignore_errors=True)
            
            shutil.copytree(self.source_dir, self.install_path)
            
            # Copy ffmpeg if it's in the root
            ffmpeg_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
            if os.path.exists(ffmpeg_src):
                shutil.copy2(ffmpeg_src, os.path.join(self.install_path, "ffmpeg.exe"))

            self.progress.set(0.7)
            self.status_label.configure(text="Creating shortcuts...")
            self.update_idletasks()
            
            self.create_shortcut()
            
            self.progress.set(1.0)
            self.status_label.configure(text="Installation Complete!")
            self.install_btn.configure(text="FINISH", state="normal", command=self.destroy)
            
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
            self.install_btn.configure(state="normal")

    def create_shortcut(self):
        # This part requires winshell or pywin32, which we have
        import pythoncom
        from win32com.client import Dispatch
        
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        path = os.path.join(desktop, "NeoRecorder.lnk")
        target = os.path.join(self.install_path, "NeoRecorder.exe")
        w_dir = self.install_path
        icon = target

        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = w_dir
        shortcut.IconLocation = icon
        shortcut.save()

if __name__ == "__main__":
    app = NeoInstaller()
    app.mainloop()
