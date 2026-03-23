import sys
import os
import types
import signal
import traceback
import importlib.util

# Write crash log
def _write_crash(exc_type, exc_value, exc_tb):
    try:
        crash_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[CRASH] {crash_text}")
        for path in ["/sdcard/rns_crash.txt", "/sdcard/Download/rns_crash.txt"]:
            try:
                with open(path, "w") as f:
                    f.write(crash_text)
                break
            except Exception:
                pass
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _write_crash

# Stub _bz2
if '_bz2' not in sys.modules:
    try:
        import _bz2
    except ImportError:
        mod = types.ModuleType('_bz2')
        class BZ2Compressor:
            def __init__(self, *a, **kw): pass
            def compress(self, data): return data
            def flush(self): return b''
        class BZ2Decompressor:
            def __init__(self, *a, **kw):
                self.unused_data = b''
                self.needs_input = True
                self.eof = False
            def decompress(self, data, *a, **kw): return data
        mod.BZ2Compressor = BZ2Compressor
        mod.BZ2Decompressor = BZ2Decompressor
        sys.modules['_bz2'] = mod

# Stub signal.signal for background thread
_real_signal = signal.signal
def _safe_signal(sig, handler):
    try:
        return _real_signal(sig, handler)
    except (ValueError, OSError):
        pass
signal.signal = _safe_signal

# Stub usbserial4a with serial4a submodule
# RNS does: from usbserial4a import serial4a
# then: serial4a.Serial(port, baudrate, ...)
if 'usbserial4a' not in sys.modules:
    try:
        import usbserial4a
        print("[STUB] real usbserial4a found")
    except ImportError:
        # Create serial4a submodule with a Serial class
        serial4a_mod = types.ModuleType('usbserial4a.serial4a')

        class Serial:
            """Stub Serial that reads/writes via the BT socket opened by bt_interface."""
            def __init__(self, port, baudrate=115200, timeout=1, *args, **kwargs):
                self.port     = port
                self.baudrate = baudrate
                self.timeout  = timeout
                self._socket  = None
                self._in_stream  = None
                self._out_stream = None
                self.is_open  = False
                print(f"[STUB] Serial({port}, {baudrate})")

            def open(self):
                try:
                    from bt_interface import _bt_socket
                    if _bt_socket is not None:
                        self._socket     = _bt_socket
                        self._in_stream  = _bt_socket.getInputStream()
                        self._out_stream = _bt_socket.getOutputStream()
                        self.is_open     = True
                        print("[STUB] Serial.open() ? using BT socket")
                    else:
                        print("[STUB] Serial.open() ? no BT socket available")
                except Exception as e:
                    print(f"[STUB] Serial.open() error: {e}")

            def close(self):
                self.is_open = False

            def read(self, size=1):
                if self._in_stream is None:
                    return b''
                try:
                    buf = [0] * size
                    n   = self._in_stream.read(buf, 0, size)
                    if n <= 0:
                        return b''
                    return bytes(buf[:n])
                except Exception:
                    return b''

            def write(self, data):
                if self._out_stream is None:
                    return 0
                try:
                    self._out_stream.write(list(data))
                    self._out_stream.flush()
                    return len(data)
                except Exception as e:
                    print(f"[STUB] write error: {e}")
                    return 0

            @property
            def in_waiting(self):
                if self._in_stream is None:
                    return 0
                try:
                    return self._in_stream.available()
                except Exception:
                    return 0

        serial4a_mod.Serial = Serial
        serial4a_mod.__spec__ = importlib.util.spec_from_loader(
            'usbserial4a.serial4a', loader=None)

        # Create parent usbserial4a module
        usb_mod = types.ModuleType('usbserial4a')
        usb_mod.__spec__ = importlib.util.spec_from_loader(
            'usbserial4a', loader=None)
        usb_mod.__spec__.submodule_search_locations = []
        usb_mod.__path__   = []
        usb_mod.__file__   = None
        usb_mod.serial4a   = serial4a_mod
        usb_mod.Serial     = Serial

        sys.modules['usbserial4a']         = usb_mod
        sys.modules['usbserial4a.serial4a'] = serial4a_mod
        print("[STUB] usbserial4a + serial4a stubbed")

import threading
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.clock import Clock
from kivy.core.window import Window

from screens.chat_screen import ChatScreen
from screens.contacts_screen import ContactsScreen
from screens.settings_screen import SettingsScreen

from bt_interface import write_rns_config
from rns_backend import RNSBackend, APP_DIR, RNS_CONFIG


class RNSMessengerApp(App):

    def build(self):
        Window.clearcolor = (0.07, 0.07, 0.10, 1)
        self.backend = RNSBackend()
        self.backend.on_rns_ready = self._on_rns_ready
        self.backend.on_message   = self._on_message_received
        self.sm = ScreenManager(transition=SlideTransition())
        self.sm.add_widget(ContactsScreen(name="contacts", app=self))
        self.sm.add_widget(ChatScreen(name="chat",         app=self))
        self.sm.add_widget(SettingsScreen(name="settings", app=self))
        self.sm.current = "contacts"
        threading.Thread(target=self._start_rns, daemon=True).start()
        return self.sm

    def _start_rns(self):
        error_msg = None
        try:
            settings = self._load_settings()
            write_rns_config(
                config_dir=RNS_CONFIG,
                bt_port=settings.get("bt_port", "/dev/rfcomm0"),
                frequency=settings.get("frequency", 433025000),
                bandwidth=settings.get("bandwidth", 125000),
                txpower=settings.get("txpower", 17),
                sf=settings.get("sf", 8),
                cr=settings.get("cr", 6),
            )
            self.backend.start()
        except Exception as e:
            error_msg = str(e)[:50]
            tb = traceback.format_exc()
            print(f"[RNS] Startup error:\n{tb}")
            for path in ["/sdcard/rns_crash.txt", "/sdcard/Download/rns_crash.txt"]:
                try:
                    with open(path, "w") as f:
                        f.write(tb)
                    break
                except Exception:
                    pass

        if error_msg is not None:
            msg = error_msg
            Clock.schedule_once(lambda dt: self._notify_rns_error(msg))

    def _notify_rns_error(self, msg):
        try:
            self.sm.get_screen("contacts").set_my_address(f"RNS offline: {msg}")
        except Exception:
            pass

    def _on_rns_ready(self):
        Clock.schedule_once(lambda dt: self._notify_ui_rns_ready())

    def _notify_ui_rns_ready(self):
        self.sm.get_screen("contacts").set_my_address(self.backend.my_address)

    def _on_message_received(self, parsed_msg):
        Clock.schedule_once(lambda dt: self._dispatch_message(parsed_msg))

    def _dispatch_message(self, parsed_msg):
        self.sm.get_screen("chat").receive_message(parsed_msg)

    def navigate_to_chat(self, contact_hash, contact_name):
        chat = self.sm.get_screen("chat")
        chat.set_contact(contact_hash, contact_name)
        self.sm.current = "chat"

    def _load_settings(self):
        settings = {}
        path = os.path.join(APP_DIR, "settings.cfg")
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        try:
                            settings[k.strip()] = int(v.strip())
                        except ValueError:
                            settings[k.strip()] = v.strip()
        return settings

    def save_settings(self, settings):
        path = os.path.join(APP_DIR, "settings.cfg")
        with open(path, "w") as f:
            for k, v in settings.items():
                f.write(f"{k} = {v}\n")


if __name__ == "__main__":
    RNSMessengerApp().run()
