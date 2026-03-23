import os
import time
import threading
import RNS
import LXMF

# Android-compatible storage path
def _get_app_dir():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        files_dir = context.getFilesDir().getAbsolutePath()
        return os.path.join(files_dir, "rns_messenger")
    except Exception:
        # Fallback for non-Android (desktop testing)
        return os.path.expanduser("~/.rns_messenger")

APP_DIR       = _get_app_dir()
IDENTITY_FILE = os.path.join(APP_DIR, "identity")
LXMF_DIR      = os.path.join(APP_DIR, "lxmf")
RNS_CONFIG    = os.path.join(APP_DIR, "config")

OPPORTUNISTIC_MAX = 250


class RNSBackend:

    def __init__(self):
        self.reticulum        = None
        self.router           = None
        self.identity         = None
        self.local_dest       = None
        self.running          = False
        self.on_message       = None
        self.on_state_change  = None
        self.on_rns_ready     = None

        os.makedirs(APP_DIR,  exist_ok=True)
        os.makedirs(LXMF_DIR, exist_ok=True)

    def start(self):
        self.reticulum = RNS.Reticulum(configdir=RNS_CONFIG)
        self.router = LXMF.LXMRouter(
            storagepath=LXMF_DIR,
            enforce_stamps=False,
        )
        self.identity   = self._load_or_create_identity()
        self.local_dest = self.router.register_delivery_identity(
            self.identity,
            display_name=b"RNS Messenger",
        )
        self.router.register_delivery_callback(self._on_message_received)
        self.local_dest.announce()
        self.running = True
        if self.on_rns_ready:
            self.on_rns_ready()

    def stop(self):
        self.running = False

    def _load_or_create_identity(self):
        if os.path.exists(IDENTITY_FILE):
            return RNS.Identity.from_file(IDENTITY_FILE)
        identity = RNS.Identity()
        identity.to_file(IDENTITY_FILE)
        return identity

    @property
    def my_address(self):
        if self.local_dest:
            return RNS.prettyhexrep(self.local_dest.hash)
        return None

    @property
    def my_address_bytes(self):
        if self.local_dest:
            return self.local_dest.hash
        return None

    def send_text(self, recipient_hash_hex, text, on_delivered=None, on_failed=None):
        recipient_hash = bytes.fromhex(recipient_hash_hex.replace("<","").replace(">","").strip())
        dest = self._resolve_destination(recipient_hash)
        if dest is None:
            if on_failed:
                on_failed(None)
            return None
        content_bytes = text.encode("utf-8")
        if len(content_bytes) <= OPPORTUNISTIC_MAX:
            method = LXMF.LXMessage.OPPORTUNISTIC
        else:
            method = LXMF.LXMessage.DIRECT
        msg = LXMF.LXMessage(dest, self.local_dest, text, desired_method=method)
        msg.try_propagation_on_fail = True
        if on_delivered:
            msg.register_delivery_callback(lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(lambda m: on_failed(RNS.hexrep(m.hash)))
        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    def send_image(self, recipient_hash_hex, image_bytes, caption="",
                   mime_type="image/jpeg", on_delivered=None, on_failed=None):
        recipient_hash = bytes.fromhex(recipient_hash_hex.replace("<","").replace(">","").strip())
        dest = self._resolve_destination(recipient_hash)
        if dest is None:
            if on_failed:
                on_failed(None)
            return None
        fields = {
            LXMF.FIELD_IMAGE: [mime_type.encode("utf-8"), image_bytes],
        }
        msg = LXMF.LXMessage(dest, self.local_dest, caption,
                              desired_method=LXMF.LXMessage.DIRECT, fields=fields)
        msg.try_propagation_on_fail = True
        if on_delivered:
            msg.register_delivery_callback(lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(lambda m: on_failed(RNS.hexrep(m.hash)))
        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    def _on_message_received(self, message):
        parsed = {
            "source_hash": RNS.hexrep(message.source_hash),
            "title":       message.title.decode("utf-8") if message.title else "",
            "content":     message.content.decode("utf-8") if message.content else "",
            "timestamp":   message.timestamp,
            "image":       None,
            "rssi":        message.rssi,
            "snr":         message.snr,
            "method":      message.method,
        }
        fields = message.get_fields() if hasattr(message, "get_fields") else {}
        if LXMF.FIELD_IMAGE in fields:
            mime, img_bytes = fields[LXMF.FIELD_IMAGE]
            parsed["image"] = {
                "mime": mime.decode("utf-8") if isinstance(mime, bytes) else mime,
                "data": img_bytes,
            }
        if self.on_message:
            self.on_message(parsed)

    def _resolve_destination(self, recipient_hash, timeout=15):
        identity = RNS.Identity.recall(recipient_hash)
        if identity is None:
            RNS.Transport.request_path(recipient_hash)
            deadline = time.time() + timeout
            while time.time() < deadline:
                identity = RNS.Identity.recall(recipient_hash)
                if identity:
                    break
                time.sleep(0.5)
        if identity is None:
            return None
        return RNS.Destination(identity, RNS.Destination.OUT,
                               RNS.Destination.SINGLE, "lxmf", "delivery")

    def request_path(self, recipient_hash_hex):
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        RNS.Transport.request_path(h)

    def is_known(self, recipient_hash_hex):
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        return RNS.Identity.recall(h) is not None

    def announce(self):
        if self.local_dest:
            self.local_dest.announce()
