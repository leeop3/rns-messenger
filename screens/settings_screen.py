import os
import threading
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from bt_interface import (FREQUENCY_PRESETS, BANDWIDTH_PRESETS,
                          get_paired_devices, connect_bt_device,
                          disconnect_bt, is_connected,
                          request_bt_permissions)

C_TEXT    = (0.95, 0.95, 0.95, 1)
C_META    = (0.55, 0.55, 0.60, 1)
C_ACCENT  = (0.13, 0.37, 0.63, 1)
C_INPUT   = (0.12, 0.12, 0.16, 1)
C_WARN    = (0.8,  0.3,  0.3,  1)
C_GREEN   = (0.1,  0.7,  0.3,  1)
C_DISCONN = (0.5,  0.5,  0.5,  1)

ROW_H   = 72
FONT_SP = "17sp"


def _row(label_text, widget):
    row = BoxLayout(size_hint_y=None, height=ROW_H, spacing=10, padding=(0, 4))
    row.add_widget(Label(text=label_text, color=C_META, size_hint_x=0.40,
                         halign="right", valign="middle", font_size=FONT_SP))
    row.add_widget(widget)
    return row


def _spinner(text, values):
    return Spinner(text=text, values=values,
                   size_hint_y=None, height=ROW_H,
                   font_size=FONT_SP,
                   background_color=C_INPUT, color=C_TEXT)


class SettingsScreen(Screen):

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        # Top bar
        topbar = BoxLayout(size_hint_y=None, height=64, padding=(8, 4))
        with topbar.canvas.before:
            Color(0.10, 0.10, 0.14, 1)
            self._tb = RoundedRectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: setattr(self._tb, "pos", topbar.pos),
                    size=lambda *a: setattr(self._tb, "size", topbar.size))
        back = Button(text="? Back", size_hint_x=None, width=100,
                      background_color=(0, 0, 0, 0), color=C_TEXT, font_size=FONT_SP)
        back.bind(on_press=lambda *a: setattr(self.manager, "current", "contacts"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="Settings", color=C_TEXT,
                                font_size="20sp", bold=True))
        root.add_widget(topbar)

        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=8, padding=(16, 12))
        content.bind(minimum_height=content.setter("height"))

        # BT Device
        content.add_widget(self._section("RNode Bluetooth"))

        # Permission status
        self.perm_label = Label(
            text="Bluetooth permissions: checking...",
            color=C_META, font_size="13sp",
            size_hint_y=None, height=36, halign="left")
        content.add_widget(self.perm_label)

        self.device_spinner = _spinner("Tap Scan to find devices", ["Tap Scan to find devices"])
        self.device_spinner.background_color = C_ACCENT
        content.add_widget(_row("BT Device", self.device_spinner))

        # Status + connect row
        conn_row = BoxLayout(size_hint_y=None, height=ROW_H, spacing=8)
        self.status_label = Label(
            text="? Disconnected", color=C_DISCONN,
            font_size=FONT_SP, size_hint_x=0.5, halign="center")
        self.connect_btn = Button(
            text="Connect", size_hint_x=0.5,
            background_color=C_GREEN, color=C_TEXT, font_size=FONT_SP)
        self.connect_btn.bind(on_press=self._on_connect)
        conn_row.add_widget(self.status_label)
        conn_row.add_widget(self.connect_btn)
        content.add_widget(conn_row)

        # Scan button
        scan_btn = Button(
            text="?? Scan Paired BT Devices",
            size_hint_y=None, height=64,
            background_color=C_INPUT, color=C_TEXT, font_size=FONT_SP)
        scan_btn.bind(on_press=lambda *a: self._request_and_scan())
        content.add_widget(scan_btn)

        # LoRa
        content.add_widget(self._section("LoRa Parameters"))

        self.freq_spinner = _spinner("433.025 MHz", list(FREQUENCY_PRESETS.keys()))
        self.freq_spinner.background_color = C_ACCENT
        content.add_widget(_row("Frequency", self.freq_spinner))

        self.bw_spinner = _spinner("125 kHz", list(BANDWIDTH_PRESETS.keys()))
        content.add_widget(_row("Bandwidth", self.bw_spinner))

        self.sf_spinner = _spinner("8", [str(x) for x in range(7, 13)])
        content.add_widget(_row("Spreading Factor", self.sf_spinner))

        self.cr_spinner = _spinner("6", ["5", "6", "7", "8"])
        content.add_widget(_row("Coding Rate", self.cr_spinner))

        self.txpower_in = TextInput(
            text="17", multiline=False, size_hint_y=None, height=ROW_H,
            background_color=C_INPUT, foreground_color=C_TEXT, font_size=FONT_SP)
        content.add_widget(_row("TX Power (dBm)", self.txpower_in))

        content.add_widget(self._section("Active Config"))
        self.config_label = Label(
            text="433.025 MHz | 125 kHz | SF8 | CR6 | 17dBm",
            color=C_META, font_size="14sp",
            size_hint_y=None, height=40, halign="left")
        content.add_widget(self.config_label)

        content.add_widget(self._section("Identity"))
        self.identity_label = Label(
            text="Loading...", color=C_META, font_size="13sp",
            size_hint_y=None, height=40, halign="left")
        content.add_widget(self.identity_label)

        reset_btn = Button(
            text="Reset Identity (creates new address)",
            size_hint_y=None, height=64,
            background_color=C_WARN, color=C_TEXT, font_size=FONT_SP)
        reset_btn.bind(on_press=self._reset_identity)
        content.add_widget(reset_btn)

        save_btn = Button(
            text="Save & Restart RNS",
            size_hint_y=None, height=72,
            background_color=C_ACCENT, color=C_TEXT, font_size="18sp")
        save_btn.bind(on_press=self._save)
        content.add_widget(save_btn)

        scroll = ScrollView()
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self, *args):
        settings = self.app._load_settings()
        self.freq_spinner.text = settings.get("frequency_label", "433.025 MHz")
        self.bw_spinner.text   = settings.get("bandwidth_label", "125 kHz")
        self.sf_spinner.text   = str(settings.get("sf", 8))
        self.cr_spinner.text   = str(settings.get("cr", 6))
        self.txpower_in.text   = str(settings.get("txpower", 17))
        addr = self.app.backend.my_address or "Not yet initialised"
        self.identity_label.text = f"Address: {addr}"
        self._update_config_label()
        self._update_conn_status()
        # Auto-request permissions on enter
        self._request_and_scan()

    def _request_and_scan(self):
        self.perm_label.text  = "Requesting Bluetooth permissions..."
        self.perm_label.color = (0.9, 0.7, 0.1, 1)

        def on_permission(granted):
            if granted:
                Clock.schedule_once(lambda dt: self._set_perm_label("? Permissions granted", C_GREEN))
                Clock.schedule_once(lambda dt: self._scan_devices())
            else:
                Clock.schedule_once(lambda dt: self._set_perm_label(
                    "? BT permission denied ? grant in Android Settings", C_WARN))

        # Must call from main thread
        request_bt_permissions(on_permission)

    def _set_perm_label(self, text, color):
        self.perm_label.text  = text
        self.perm_label.color = color

    def _scan_devices(self):
        self.device_spinner.text   = "Scanning..."
        self.device_spinner.values = ["Scanning..."]
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        devices = get_paired_devices()
        Clock.schedule_once(lambda dt: self._populate_devices(devices))

    def _populate_devices(self, devices):
        self.device_spinner.values = devices
        saved = self.app._load_settings().get("bt_device_name", "")
        self.device_spinner.text = saved if saved in devices else devices[0]

    def _on_connect(self, *args):
        device_name = self.device_spinner.text
        if not device_name or device_name in (
                "Scanning...", "No paired devices",
                "Tap Scan to find devices", "BT not enabled - enable BT first",
                "No BT adapter"):
            return

        if is_connected():
            disconnect_bt()
            self._update_conn_status()
            return

        self.status_label.text  = "? Connecting..."
        self.status_label.color = (0.9, 0.7, 0.1, 1)
        self.connect_btn.disabled = True

        def do_connect():
            success, result = connect_bt_device(device_name)
            Clock.schedule_once(
                lambda dt: self._on_connect_result(success, result, device_name))

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_connect_result(self, success, result, device_name):
        self.connect_btn.disabled = False
        if success:
            self.status_label.text  = f"? Connected: {device_name}"
            self.status_label.color = C_GREEN
            self.connect_btn.text   = "Disconnect"
            settings = self.app._load_settings()
            settings["bt_device_name"] = device_name
            self.app.save_settings(settings)
        else:
            self.status_label.text  = f"? Failed: {result[:35]}"
            self.status_label.color = C_WARN
            self.connect_btn.text   = "Connect"

    def _update_conn_status(self):
        if is_connected():
            self.status_label.text  = "? Connected"
            self.status_label.color = C_GREEN
            self.connect_btn.text   = "Disconnect"
        else:
            self.status_label.text  = "? Disconnected"
            self.status_label.color = C_DISCONN
            self.connect_btn.text   = "Connect"

    def _save(self, *args):
        freq_label = self.freq_spinner.text
        bw_label   = self.bw_spinner.text
        settings = {
            "bt_device_name":  self.device_spinner.text,
            "frequency_label": freq_label,
            "bandwidth_label": bw_label,
            "frequency":       FREQUENCY_PRESETS.get(freq_label, 433025000),
            "bandwidth":       BANDWIDTH_PRESETS.get(bw_label, 125000),
            "sf":              int(self.sf_spinner.text),
            "cr":              int(self.cr_spinner.text),
            "txpower":         int(self.txpower_in.text or "17"),
        }
        self.app.save_settings(settings)
        self._update_config_label()
        from rns_backend import RNS_CONFIG
        config_path = os.path.join(RNS_CONFIG, "config")
        if os.path.exists(config_path):
            os.remove(config_path)
        self.identity_label.text = "Saved. Restart app to apply."

    def _reset_identity(self, *args):
        from rns_backend import IDENTITY_FILE
        if os.path.exists(IDENTITY_FILE):
            os.remove(IDENTITY_FILE)
        self.identity_label.text = "Identity reset. Restart app for new address."

    def _update_config_label(self):
        self.config_label.text = (
            f"{self.freq_spinner.text} | {self.bw_spinner.text} | "
            f"SF{self.sf_spinner.text} | CR{self.cr_spinner.text} | "
            f"{self.txpower_in.text}dBm"
        )

    def _section(self, title):
        return Label(text=title, color=C_ACCENT, font_size="15sp", bold=True,
                     size_hint_y=None, height=44, halign="left")
