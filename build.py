
import os
import subprocess
import sys

def build():
    try:
        import PyInstaller.__main__
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        import PyInstaller.__main__

    # Convert PNG icon to ICO if it exists
    png_icon = "app_icon.png"
    icon_path = "app_icon.ico"
    if os.path.exists(png_icon):
        try:
            from PIL import Image
            print(f"Converting {png_icon} to {icon_path}...")
            img = Image.open(png_icon)
            img.save(icon_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        except Exception as e:
            print(f"Warning: Could not convert icon: {e}")

    if not os.path.exists(icon_path):
        print(f"Warning: {icon_path} not found. Building without custom exe icon.")
        icon_arg = []
    else:
        icon_arg = [f'--icon={icon_path}']

    # Check for FFmpeg to bundle
    ffmpeg_exe = "ffmpeg.exe"
    ffmpeg_arg = []
    if os.path.exists(ffmpeg_exe):
        print(f"Found {ffmpeg_exe}, bundling into EXE...")
        ffmpeg_arg = [f'--add-binary={ffmpeg_exe};.']
    else:
        print(f"Warning: {ffmpeg_exe} not found in root. It won't be bundled.")

    # Hidden imports for dependencies that PyInstaller might miss
    hidden_imports = [
        '--hidden-import=pycaw',
        '--hidden-import=pycaw.pycaw',
        '--hidden-import=comtypes',
        '--hidden-import=comtypes.client',
        '--hidden-import=winotify',
        '--hidden-import=win32gui',
        '--hidden-import=win32process',
        '--hidden-import=psutil',
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=pyaudio',
        '--hidden-import=numpy',
        '--hidden-import=pystray',
        '--hidden-import=pystray._win32',
        '--hidden-import=keyboard',
        '--hidden-import=mss',
        '--hidden-import=mss.windows',
        '--hidden-import=plyer',
        '--hidden-import=plyer.platforms.win.notification',
        '--hidden-import=plyer.platforms.notification',
        '--hidden-import=ttkbootstrap',
        '--hidden-import=ttkbootstrap.toast',
    ]

    # Prepare command
    cmd = [
        'main.py',
        '--onefile',
        '--noconsole',
        '--name=NeoRecorder',
        '--add-data=assets;assets',
        '--add-data=app_icon.ico;.',
        '--collect-all=customtkinter',
    ] + icon_arg + ffmpeg_arg + hidden_imports

    print(f"Running PyInstaller with: {' '.join(cmd)}")
    print("\nThis may take several minutes...")
    
    PyInstaller.__main__.run(cmd)
    
    print("\n" + "="*50)
    print("Build complete!")
    print(f"Output: dist/NeoRecorder.exe")
    print("="*50)

def install_dependencies():
    """Install all required dependencies"""
    deps = [
        "customtkinter",
        "pillow",
        "pyaudio",
        "numpy",
        "pywin32",
        "psutil",
        "pycaw",
        "winotify",
        "pyinstaller"
    ]
    
    print("Installing dependencies...")
    for dep in deps:
        print(f"  Installing {dep}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            print(f"    Warning: Could not install {dep}")
    print("Dependencies installed!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--deps":
        install_dependencies()
    else:
        build()
