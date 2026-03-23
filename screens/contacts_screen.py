import os
import json

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle

from rns_backend import APP_DIR

C_TEXT   = (0.95, 0.95, 0.95, 1)
C_META   = (0.55, 0.55, 0.60, 1)
C_ACCENT = (0.13, 0.37, 0.63, 1)
C_ROW_BG = (0.12, 0.12, 0.16, 1)

CONTACTS_FILE = os.path.join(APP_DIR, "contacts.json")


class ContactRow(BoxLayout):
    def __init__(self, name, address, on_chat, on_delete, **kwargs):
        super().__init__(size_hint_y=None, height=60, spacing=6, padding=(8,4), **kwargs)
        self.name = name
        self.address = address
        with self.canvas.before:
            Color(*C_ROW_BG)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
        self.bind(pos=self._upd, size=self._upd)
        info = BoxLayout(orientation="vertical")
        info.add_widget(Label(text=name, color=C_TEXT, font_size="15sp", halign="left", bold=True))
        info.add_widget(Label(text=address, color=C_META, font_size="11sp", halign="left"))
        self.add_widget(info)
        chat_btn = Button(text="💬", size_hint_x=None, width=44,
                          background_color=(0,0,0,0), color=C_TEXT, font_size="22sp")
        chat_btn.bind(on_press=lambda *a: on_chat(name, address))
        del_btn = Button(text="🗑", size_hint_x=None, width=44,
                         background_color=(0,0,0,0), color=(0.8,0.3,0.3,1), font_size="20sp")
        del_btn.bind(on_press=lambda *a: on_delete(address))
        self.add_widget(chat_btn)
        self.add_widget(del_btn)

    def _upd(self, *a):
        self._rect.pos  = self.pos
        self._rect.size = self.size


class ContactsScreen(Screen):

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.contacts = self._load_contacts()
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", spacing=0)
        topbar = BoxLayout(size_hint_y=None, height=56, padding=(12,4), spacing=8)
        with topbar.canvas.before:
            Color(0.10, 0.10, 0.14, 1)
            self._tb = RoundedRectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: setattr(self._tb,"pos",topbar.pos),
                    size=lambda *a: setattr(self._tb,"size",topbar.size))
        topbar.add_widget(Label(text="RNS Messenger", color=C_TEXT,
                                font_size="18sp", bold=True, halign="left"))
        settings_btn = Button(text="⚙", size_hint_x=None, width=44,
                              background_color=(0,0,0,0), color=C_TEXT, font_size="22sp")
        settings_btn.bind(on_press=lambda *a: setattr(self.manager,"current","settings"))
        topbar.add_widget(settings_btn)
        root.add_widget(topbar)
        addr_bar = BoxLayout(size_hint_y=None, height=44, padding=(12,4))
        self.my_addr_label = Label(text="Initialising RNS...", color=C_META,
                                   font_size="11sp", halign="left")
        addr_bar.add_widget(self.my_addr_label)
        root.add_widget(addr_bar)
        self.contact_list = BoxLayout(orientation="vertical", size_hint_y=None,
                                      spacing=6, padding=(8,4))
        self.contact_list.bind(minimum_height=self.contact_list.setter("height"))
        scroll = ScrollView(size_hint=(1,1))
        scroll.add_widget(self.contact_list)
        root.add_widget(scroll)
        add_btn = Button(text="+ Add Contact", size_hint_y=None, height=52,
                         background_color=C_ACCENT, color=C_TEXT, font_size="16sp")
        add_btn.bind(on_press=self._show_add_dialog)
        root.add_widget(add_btn)
        self.add_widget(root)
        self._refresh_list()

    def set_my_address(self, address):
        self.my_addr_label.text = f"My address: {address}"

    def _refresh_list(self):
        self.contact_list.clear_widgets()
        for addr, name in self.contacts.items():
            row = ContactRow(name=name, address=addr,
                             on_chat=self._open_chat, on_delete=self._delete_contact)
            self.contact_list.add_widget(row)

    def _open_chat(self, name, address):
        self.app.navigate_to_chat(address, name)

    def _delete_contact(self, address):
        self.contacts.pop(address, None)
        self._save_contacts()
        self._refresh_list()

    def _show_add_dialog(self, *args):
        content = BoxLayout(orientation="vertical", spacing=10, padding=12)
        name_in = TextInput(hint_text="Name", multiline=False, size_hint_y=None, height=44)
        addr_in = TextInput(hint_text="LXMF address (32 hex chars)", multiline=False,
                            size_hint_y=None, height=44)
        save_btn = Button(text="Add", size_hint_y=None, height=44,
                          background_color=C_ACCENT, color=C_TEXT)
        content.add_widget(name_in)
        content.add_widget(addr_in)
        content.add_widget(save_btn)
        popup = Popup(title="Add Contact", content=content, size_hint=(0.85, 0.4))
        def do_add(*a):
            name = name_in.text.strip()
            addr = addr_in.text.strip().lower().replace("<","").replace(">","")
            if name and len(addr) == 32:
                self.contacts[addr] = name
                self._save_contacts()
                self._refresh_list()
                popup.dismiss()
        save_btn.bind(on_press=do_add)
        popup.open()

    def _load_contacts(self):
        if os.path.exists(CONTACTS_FILE):
            try:
                with open(CONTACTS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_contacts(self):
        with open(CONTACTS_FILE, "w") as f:
            json.dump(self.contacts, f, indent=2)
