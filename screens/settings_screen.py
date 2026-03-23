import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, RoundedRectangle
from bt_interface import FREQUENCY_PRESETS

C_TEXT   = (0.95, 0.95, 0.95, 1)
C_META   = (0.55, 0.55, 0.60, 1)
C_ACCENT = (0.13, 0.37, 0.63, 1)
C_INPUT  = (0.12, 0.12, 0.16, 1)
C_WARN   = (0.8, 0.3, 0.3, 1)

def _row(label_text, widget):
    row = BoxLayout(size_hint_y=None, height=52, spacing=10, padding=(0,4))
    row.add_widget(Label(text=label_text, color=C_META, size_hint_x=0.38,
                         halign="right", valign="middle"))
    row.add_widget(widget)
    return row

class SettingsScreen(Screen):

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")
        topbar = BoxLayout(size_hint_y=None, height=56, padding=(8,4))
        with topbar.canvas.before:
            Color(0.10, 0.10, 0.14, 1)
            self._tb = RoundedRectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: setattr(self._tb,"pos",topbar.pos),
                    size=lambda *a: setattr(self._tb,"size",topbar.size))
        back = Button(text="← Back", size_hint_x=None, width=80,
                      background_color=(0,0,0,0), color=C_TEXT)
        back.bind(on_press=lambda *a: setattr(self.manager,"current","contacts"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="Settings", color=C_TEXT,
                                font_size="18sp", bold=True))
        root.add_widget(topbar)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=6, padding=(16,12))
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(self._section("RNode Bluetooth"))
        self.bt_name_in = TextInput(
            hint_text="Paired BT device name (e.g. RNode_A3B4)",
            multiline=False, size_hint_y=None, height=44,
            background_color=C_INPUT, foreground_color=C_TEXT)
        content.add_widget(_row("BT Device", self.bt_name_in))
        content.add_widget(self._section("LoRa Parameters"))
        self.freq_spinner = Spinner(
            text="EU868", values=list(FREQUENCY_PRESETS.keys()),
            size_hint_y=None, height=44,
            background_color=C_ACCENT, color=C_TEXT)
        content.add_widget(_row("Region", self.freq_spinner))
        self.bw_spinner = Spinner(
            text="125000", values=["125000","250000","500000"],
            size_hint_y=None, height=44,
            background_color=C_INPUT, color=C_TEXT)
        content.add_widget(_row("Bandwidth", self.bw_spinner))
        self.sf_spinner = Spinner(
            text="7", values=[str(x) for x in range(7,13)],
            size_hint_y=None, height=44,
            background_color=C_INPUT, color=C_TEXT)
        content.add_widget(_row("Spreading", self.sf_spinner))
        self.cr_spinner = Spinner(
            text="5", values=["5","6","7","8"],
            size_hint_y=None, height=44,
            background_color=C_INPUT, color=C_TEXT)
        content.add_widget(_row("Coding Rate", self.cr_spinner))
        self.txpower_in = TextInput(
            text="14", multiline=False, size_hint_y=None, height=44,
            background_color=C_INPUT, foreground_color=C_TEXT)
        content.add_widget(_row("TX Power (dBm)", self.txpower_in))
        content.add_widget(self._section("Identity"))
        self.identity_label = Label(
            text="Loading...", color=C_META, font_size="11sp",
            size_hint_y=None, height=36, halign="left")
        content.add_widget(self.identity_label)
        reset_btn = Button(
            text="Reset Identity (creates new address)",
            size_hint_y=None, height=48,
            background_color=C_WARN, color=C_TEXT)
        reset_btn.bind(on_press=self._reset_identity)
        content.add_widget(reset_btn)
        save_btn = Button(
            text="Save & Restart RNS",
            size_hint_y=None, height=52,
            background_color=C_ACCENT, color=C_TEXT, font_size="16sp")
        save_btn.bind(on_press=self._save)
        content.add_widget(save_btn)
        scroll = ScrollView()
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self, *args):
        settings = self.app._load_settings()
        self.bt_name_in.text   = settings.get("bt_device_name", "")
        self.freq_spinner.text = settings.get("region", "EU868")
        self.bw_spinner.text   = str(settings.get("bandwidth", 125000))
        self.sf_spinner.text   = str(settings.get("sf", 7))
        self.cr_spinner.text   = str(settings.get("cr", 5))
        self.txpower_in.text   = str(settings.get("txpower", 14))
        addr = self.app.backend.my_address or "Not yet initialised"
        self.identity_label.text = f"Address: {addr}"

    def _save(self, *args):
        region = self.freq_spinner.text
        settings = {
            "bt_device_name": self.bt_name_in.text.strip(),
            "region":         region,
            "frequency":      FREQUENCY_PRESETS.get(region, 868000000),
            "bandwidth":      int(self.bw_spinner.text),
            "sf":             int(self.sf_spinner.text),
            "cr":             int(self.cr_spinner.text),
            "txpower":        int(self.txpower_in.text or "14"),
        }
        self.app.save_settings(settings)
        self.identity_label.text = "Settings saved. Restart app to apply."

    def _reset_identity(self, *args):
        from rns_backend import IDENTITY_FILE
        if os.path.exists(IDENTITY_FILE):
            os.remove(IDENTITY_FILE)
        self.identity_label.text = "Identity reset. Restart app for new address."

    def _section(self, title):
        return Label(text=title, color=C_ACCENT, font_size="14sp", bold=True,
                     size_hint_y=None, height=36, halign="left")
