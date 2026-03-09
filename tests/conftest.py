import sys
import types
import importlib
import re
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class FakeImage:
    def __init__(self, size=(100, 50), bgra=b"\x00" * 16):
        self.size = size
        self.bgra = bgra
        self.saved = []

    def save(self, path_or_buffer, *args, **kwargs):
        self.saved.append((path_or_buffer, args, kwargs))
        payload = b"BM" + b"\x00" * 32
        if hasattr(path_or_buffer, "write"):
            path_or_buffer.write(payload)
            return

        Path(path_or_buffer).write_bytes(payload)

    def convert(self, _mode):
        return self


class FakeEnhancer:
    def __init__(self, image):
        self.image = image

    def enhance(self, _value):
        return self.image


class FakeCanvas:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.bindings = {}
        self.items = {}
        self.deleted = []
        self._next_id = 1

    def pack(self, *args, **kwargs):
        return None

    def bind(self, event, callback):
        self.bindings[event] = callback

    def create_image(self, *args, **kwargs):
        return self._create_item("image", args)

    def create_text(self, *args, **kwargs):
        return self._create_item("text", args, kwargs)

    def create_rectangle(self, *args, **kwargs):
        return self._create_item("rectangle", args, kwargs)

    def bbox(self, item_id):
        if item_id in self.items:
            return (10, 10, 110, 40)
        return None

    def coords(self, item_id, *coords):
        if item_id in self.items:
            self.items[item_id]["coords"] = coords

    def itemconfig(self, item_id, **kwargs):
        if item_id in self.items:
            self.items[item_id]["config"].update(kwargs)

    def delete(self, tag_or_id):
        self.deleted.append(tag_or_id)

    def tag_raise(self, item_id):
        return item_id

    def _create_item(self, kind, coords, config=None):
        item_id = self._next_id
        self._next_id += 1
        self.items[item_id] = {
            "kind": kind,
            "coords": coords,
            "config": config or {},
        }
        return item_id


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.children = []
        self.bindings = {}
        self.config = dict(kwargs)
        self.exists = True
        self.after_calls = []
        self.geometry_value = ""
        self.value = ""
        self.selected = False
        self.x = 100
        self.y = 100
        self.width = kwargs.get("width", 200)
        self.height = kwargs.get("height", 100)
        self.screen_width = 1920
        self.screen_height = 1080
        self.canvas = None
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def pack(self, *args, **kwargs):
        return None

    def grid(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def pack_forget(self):
        self.config["packed"] = False

    def configure(self, **kwargs):
        self.config.update(kwargs)

    config = configure

    def destroy(self):
        self.exists = False

    def bind(self, event, callback):
        self.bindings[event] = callback

    def after(self, delay, callback=None):
        self.after_calls.append((delay, callback))
        token = f"after-{len(self.after_calls)}"
        if callback and getattr(self, "run_after_immediately", False):
            callback()
        return token

    def after_cancel(self, token):
        self.config["after_cancelled"] = token

    def winfo_exists(self):
        return self.exists

    def winfo_children(self):
        return list(self.children)

    def winfo_screenwidth(self):
        return self.screen_width

    def winfo_screenheight(self):
        return self.screen_height

    def winfo_fpixels(self, _value):
        return 96.0

    def winfo_id(self):
        return 123

    def winfo_x(self):
        return self.x

    def winfo_y(self):
        return self.y

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def update_idletasks(self):
        return None

    def update(self):
        return None

    def lift(self):
        self.config["lifted"] = True

    def focus_force(self):
        self.config["focused"] = True

    def withdraw(self):
        self.config["withdrawn"] = True

    def deiconify(self):
        self.config["deiconified"] = True

    def iconify(self):
        self.config["iconified"] = True

    def protocol(self, *_args):
        return None

    def grab_set(self):
        self.config["grabbed"] = True

    def grab_release(self):
        self.config["grab_released"] = True

    def mainloop(self):
        return None

    def title(self, value):
        self.config["title"] = value

    def geometry(self, value):
        self.geometry_value = value
        size_match = re.match(r"^(?P<w>\d+)x(?P<h>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)$", value)
        if size_match:
            self.width = int(size_match.group("w"))
            self.height = int(size_match.group("h"))
            self.x = int(size_match.group("x"))
            self.y = int(size_match.group("y"))
            return

        pos_match = re.match(r"^(?P<x>[+-]\d+)(?P<y>[+-]\d+)$", value)
        if pos_match:
            self.x = int(pos_match.group("x"))
            self.y = int(pos_match.group("y"))

    def overrideredirect(self, value):
        self.config["overrideredirect"] = value

    def attributes(self, *args):
        self.config.setdefault("attributes", []).append(args)

    def iconbitmap(self, path):
        self.config["iconbitmap"] = path

    def insert(self, _index, value):
        self.value = value

    def delete(self, *_args):
        self.value = ""

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def select(self):
        self.selected = True

    def deselect(self):
        self.selected = False


class FakeTk(FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.withdrawn = False

    def withdraw(self):
        self.withdrawn = True


class FakeCTkButton(FakeWidget):
    def __init__(self, *args, command=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = command

    def invoke(self):
        if self.command:
            self.command()


class FakeCTkSwitch(FakeWidget):
    def get(self):
        return self.selected


class FakeCTkEntry(FakeWidget):
    pass


class FakeCTkComboBox(FakeWidget):
    def __init__(self, *args, values=None, command=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = values or []
        self.command = command
        self.value = self.values[0] if self.values else ""

    def configure(self, **kwargs):
        super().configure(**kwargs)
        if "values" in kwargs:
            self.values = kwargs["values"]


class FakeCTkCanvas(FakeCanvas):
    pass


def _install_tk_modules():
    tk_module = types.ModuleType("tkinter")
    tk_module.Tk = FakeTk
    tk_module.Toplevel = FakeWidget
    tk_module.Canvas = FakeCanvas
    tk_module.Frame = FakeWidget
    tk_module.Label = FakeWidget
    tk_module._default_root = None
    sys.modules["tkinter"] = tk_module

    ctk_module = types.ModuleType("customtkinter")
    ctk_module.CTk = FakeWidget
    ctk_module.CTkToplevel = FakeWidget
    ctk_module.CTkFrame = FakeWidget
    ctk_module.CTkLabel = FakeWidget
    ctk_module.CTkButton = FakeCTkButton
    ctk_module.CTkSwitch = FakeCTkSwitch
    ctk_module.CTkComboBox = FakeCTkComboBox
    ctk_module.CTkEntry = FakeCTkEntry
    ctk_module.CTkScrollableFrame = FakeWidget
    ctk_module.CTkCanvas = FakeCTkCanvas
    ctk_module.CTkImage = FakeWidget
    ctk_module.filedialog = types.SimpleNamespace(askdirectory=lambda **_kwargs: "")
    sys.modules["customtkinter"] = ctk_module


def _install_windows_stubs():
    pyaudio_module = types.ModuleType("pyaudio")
    pyaudio_module.paInt16 = 8
    pyaudio_module.PyAudio = lambda: None
    sys.modules["pyaudio"] = pyaudio_module

    win32gui_module = types.ModuleType("win32gui")
    win32gui_module.EnumWindows = lambda handler, ctx: None
    win32gui_module.IsWindowVisible = lambda _hwnd: True
    win32gui_module.GetWindowText = lambda _hwnd: ""
    win32gui_module.GetWindowRect = lambda _hwnd: (0, 0, 100, 100)
    sys.modules["win32gui"] = win32gui_module

    sys.modules["win32process"] = types.ModuleType("win32process")
    sys.modules["psutil"] = types.ModuleType("psutil")

    mss_module = types.ModuleType("mss")
    mss_module.mss = lambda: None
    sys.modules["mss"] = mss_module
    sys.modules["mss.tools"] = types.ModuleType("mss.tools")


def _install_pillow_stubs():
    image_module = types.ModuleType("PIL.Image")
    image_module.Image = FakeImage
    image_module.frombytes = lambda *_args, **_kwargs: FakeImage()
    image_module.new = lambda *_args, **_kwargs: FakeImage()
    image_module.open = lambda *_args, **_kwargs: FakeImage()

    image_grab_module = types.ModuleType("PIL.ImageGrab")
    image_grab_module.grab = lambda *args, **kwargs: FakeImage()

    image_tk_module = types.ModuleType("PIL.ImageTk")
    image_tk_module.PhotoImage = lambda image: image

    image_enhance_module = types.ModuleType("PIL.ImageEnhance")
    image_enhance_module.Brightness = lambda image: FakeEnhancer(image)

    pil_module = types.ModuleType("PIL")
    pil_module.Image = image_module
    pil_module.ImageGrab = image_grab_module
    pil_module.ImageTk = image_tk_module
    pil_module.ImageEnhance = image_enhance_module

    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = image_module
    sys.modules["PIL.ImageGrab"] = image_grab_module
    sys.modules["PIL.ImageTk"] = image_tk_module
    sys.modules["PIL.ImageEnhance"] = image_enhance_module


_install_tk_modules()
_install_windows_stubs()
_install_pillow_stubs()


def import_fresh(module_name):
    top_level = module_name.split(".", 1)[0]
    if top_level in {"core", "gui", "utils"}:
        sys.modules.pop(top_level, None)

    for name in list(sys.modules):
        if name == module_name or name.startswith(f"{module_name}."):
            del sys.modules[name]
    return importlib.import_module(module_name)


@pytest.fixture
def fresh_import():
    return import_fresh


@pytest.fixture(autouse=True)
def reset_singletons():
    yield

    logger_module = sys.modules.get("utils.logger")
    if logger_module:
        for logger in getattr(logger_module, "_loggers", {}).values():
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
        logger_module._loggers.clear()

    for module_name in [
        "config",
        "utils.logger",
        "utils.hotkeys",
        "utils.screenshot",
        "utils.display_manager",
    ]:
        sys.modules.pop(module_name, None)


@pytest.fixture
def fake_image():
    return FakeImage()


@pytest.fixture
def fake_widget():
    return FakeWidget()
