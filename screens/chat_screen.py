import io
import time
import threading
import os

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage

C_BUBBLE_TX = (0.13, 0.37, 0.63, 1)
C_BUBBLE_RX = (0.18, 0.18, 0.22, 1)
C_TEXT      = (0.95, 0.95, 0.95, 1)
C_META      = (0.55, 0.55, 0.60, 1)
C_INPUT_BG  = (0.12, 0.12, 0.16, 1)
C_SEND_BTN  = (0.13, 0.37, 0.63, 1)


class MessageBubble(BoxLayout):
    def __init__(self, content="", image_data=None, timestamp=None,
                 is_mine=True, status="⏳", rssi=None, snr=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                         padding=4, spacing=2, **kwargs)
        self.bind(minimum_height=self.setter("height"))
        bg_color = C_BUBBLE_TX if is_mine else C_BUBBLE_RX
        halign   = "right" if is_mine else "left"
        with self.canvas.before:
            Color(*bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update_rect, size=self._update_rect)
        if image_data:
            try:
                buf = io.BytesIO(image_data)
                core_img = CoreImage(buf, ext="jpg")
                img_widget = KivyImage(texture=core_img.texture,
                                       size_hint_y=None, height=200)
                self.add_widget(img_widget)
            except Exception:
                pass
        if content:
            lbl = Label(text=content, size_hint_y=None, text_size=(280, None),
                        halign=halign, valign="top", color=C_TEXT,
                        font_size="14sp", padding=(8, 4))
            lbl.bind(texture_size=lbl.setter("size"))
            self.add_widget(lbl)
        ts_str = time.strftime("%H:%M", time.localtime(timestamp or time.time()))
        signal = f"  📶{rssi}dBm" if rssi is not None else ""
        self.status_label = Label(
            text=f"{ts_str}  {status}{signal}",
            size_hint_y=None, height=18,
            halign=halign, color=C_META, font_size="11sp")
        self.add_widget(self.status_label)

    def update_status(self, status):
        parts = self.status_label.text.rsplit("  ", 1)
        base  = parts[0] if len(parts) > 1 else self.status_label.text
        self.status_label.text = f"{base}  {status}"

    def _update_rect(self, *args):
        self._rect.pos  = self.pos
        self._rect.size = self.size


class ChatScreen(Screen):

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app          = app
        self.contact_hash = None
        self.contact_name = "Unknown"
        self._msg_widgets = {}
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", spacing=0)
        topbar = BoxLayout(size_hint_y=None, height=52, padding=(8,4))
        with topbar.canvas.before:
            Color(0.10, 0.10, 0.14, 1)
            self._topbar_rect = RoundedRectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: setattr(self._topbar_rect,"pos",topbar.pos),
                    size=lambda *a: setattr(self._topbar_rect,"size",topbar.size))
        back_btn = Button(text="← Back", size_hint_x=None, width=80,
                          background_color=(0,0,0,0), color=C_TEXT)
        back_btn.bind(on_press=lambda *a: setattr(self.manager,"current","contacts"))
        self.contact_label = Label(text=self.contact_name, color=C_TEXT,
                                   font_size="17sp", bold=True, halign="left")
        topbar.add_widget(back_btn)
        topbar.add_widget(self.contact_label)
        root.add_widget(topbar)
        self.msg_list = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=6, padding=(8,8))
        self.msg_list.bind(minimum_height=self.msg_list.setter("height"))
        self.scroll = ScrollView(size_hint=(1,1))
        self.scroll.add_widget(self.msg_list)
        root.add_widget(self.scroll)
        inputbar = BoxLayout(size_hint_y=None, height=56, spacing=6, padding=(8,4))
        with inputbar.canvas.before:
            Color(0.10, 0.10, 0.14, 1)
            self._inp_rect = RoundedRectangle(pos=inputbar.pos, size=inputbar.size)
        inputbar.bind(pos=lambda *a: setattr(self._inp_rect,"pos",inputbar.pos),
                      size=lambda *a: setattr(self._inp_rect,"size",inputbar.size))
        img_btn = Button(text="📷", size_hint_x=None, width=44,
                         background_color=(0,0,0,0), color=C_TEXT, font_size="22sp")
        img_btn.bind(on_press=self._pick_image)
        self.text_input = TextInput(
            hint_text="Message...", multiline=False, size_hint_x=1,
            background_color=C_INPUT_BG, foreground_color=C_TEXT,
            hint_text_color=C_META, cursor_color=C_TEXT, font_size="15sp")
        self.text_input.bind(on_text_validate=self._send_text)
        send_btn = Button(text="Send", size_hint_x=None, width=70,
                          background_color=C_SEND_BTN, color=C_TEXT, font_size="15sp")
        send_btn.bind(on_press=self._send_text)
        inputbar.add_widget(img_btn)
        inputbar.add_widget(self.text_input)
        inputbar.add_widget(send_btn)
        root.add_widget(inputbar)
        self.add_widget(root)

    def set_contact(self, contact_hash, contact_name):
        self.contact_hash = contact_hash
        self.contact_name = contact_name
        self.contact_label.text = contact_name
        self.msg_list.clear_widgets()
        self._msg_widgets.clear()

    def receive_message(self, parsed_msg):
        src = parsed_msg["source_hash"]
        if src != (self.contact_hash or "").strip("<> "):
            return
        image_data = None
        if parsed_msg.get("image"):
            image_data = parsed_msg["image"]["data"]
        bubble = MessageBubble(
            content=parsed_msg["content"], image_data=image_data,
            timestamp=parsed_msg["timestamp"], is_mine=False,
            status="", rssi=parsed_msg.get("rssi"))
        self._add_bubble(bubble)

    def _send_text(self, *args):
        text = self.text_input.text.strip()
        if not text or not self.contact_hash:
            return
        self.text_input.text = ""
        bubble = MessageBubble(content=text, timestamp=time.time(),
                               is_mine=True, status="⏳")
        self._add_bubble(bubble)
        def on_delivered(hash_hex):
            Clock.schedule_once(lambda dt: bubble.update_status("✓✓"))
        def on_failed(hash_hex):
            Clock.schedule_once(lambda dt: bubble.update_status("✗"))
        threading.Thread(
            target=self.app.backend.send_text,
            args=(self.contact_hash, text),
            kwargs={"on_delivered": on_delivered, "on_failed": on_failed},
            daemon=True).start()
        Clock.schedule_once(lambda dt: bubble.update_status("✓"), 0.5)

    def _pick_image(self, *args):
        chooser = FileChooserListView(
            filters=["*.jpg", "*.jpeg", "*.png"],
            path=os.path.expanduser("~"))
        popup = Popup(title="Select Image", content=chooser, size_hint=(0.9, 0.8))
        chooser.bind(on_submit=lambda fc, sel, touch: self._send_image_file(sel, popup))
        popup.open()

    def _send_image_file(self, selection, popup):
        popup.dismiss()
        if not selection or not self.contact_hash:
            return
        path = selection[0]
        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            print(f"[Chat] Failed to read image: {e}")
            return
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        bubble = MessageBubble(image_data=image_bytes, timestamp=time.time(),
                               is_mine=True, status="⏳")
        self._add_bubble(bubble)
        threading.Thread(
            target=self.app.backend.send_image,
            args=(self.contact_hash, image_bytes),
            kwargs={"mime_type": mime},
            daemon=True).start()

    def _add_bubble(self, bubble):
        self.msg_list.add_widget(bubble)
        Clock.schedule_once(lambda dt: self._scroll_bottom(), 0.1)

    def _scroll_bottom(self):
        self.scroll.scroll_y = 0

    def _update_bubble(self, hash_hex, status):
        if hash_hex in self._msg_widgets:
            self._msg_widgets[hash_hex].update_status(status)
