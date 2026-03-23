import sys
import os
import types

# Stub _bz2 for Android
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

import threading
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.clock import Clock
from kivy.core.window import Window

from screens.chat_screen import ChatScreen
from screens.contacts_screen import ContactsScreen
from screens.settings_screen import SettingsScreen

from bt_interface import write_rns_config, FREQUENCY_PRESETS
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
            print(f"[RNS] Startup error: {error_msg}")

        if error_msg is not None:
            msg = error_msg  # capture in local var for lambda
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
