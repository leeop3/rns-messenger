"""
RNS/LXMF Backend Engine
Handles identity, messaging, image transfer, path discovery.
"""

import os
import time
import threading
import RNS
import LXMF

# Storage paths (Android-compatible)
APP_DIR       = os.path.expanduser("~/.rns_messenger")
IDENTITY_FILE = os.path.join(APP_DIR, "identity")
LXMF_DIR      = os.path.join(APP_DIR, "lxmf")
RNS_CONFIG    = os.path.join(APP_DIR, "config")

# Delivery auto-select threshold (bytes)
OPPORTUNISTIC_MAX = 250  # Stay safely under 295-byte limit


class RNSBackend:
    """
    Core RNS/LXMF engine.
    Call start() once at app launch.
    All callbacks are fired on background threads — dispatch to UI thread as needed.
    """

    def __init__(self):
        self.reticulum        = None
        self.router           = None
        self.identity         = None
        self.local_dest       = None
        self.running          = False

        # Callbacks — set these from UI layer
        self.on_message       = None   # fn(message)
        self.on_state_change  = None   # fn(msg_hash_hex, state_int)
        self.on_rns_ready     = None   # fn()

        os.makedirs(APP_DIR,  exist_ok=True)
        os.makedirs(LXMF_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Startup / Shutdown                                                  #
    # ------------------------------------------------------------------ #

    def start(self):
        """Initialise RNS + LXMF. Blocks briefly; call from background thread."""
        self.reticulum = RNS.Reticulum(configdir=RNS_CONFIG)

        self.router = LXMF.LXMRouter(
            storagepath=LXMF_DIR,
            enforce_stamps=False,       # Disable spam-proof-of-work for now
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

    # ------------------------------------------------------------------ #
    #  Identity                                                            #
    # ------------------------------------------------------------------ #

    def _load_or_create_identity(self):
        if os.path.exists(IDENTITY_FILE):
            return RNS.Identity.from_file(IDENTITY_FILE)
        identity = RNS.Identity()
        identity.to_file(IDENTITY_FILE)
        return identity

    @property
    def my_address(self):
        """Our LXMF address as hex string — share this with contacts."""
        if self.local_dest:
            return RNS.prettyhexrep(self.local_dest.hash)
        return None

    @property
    def my_address_bytes(self):
        if self.local_dest:
            return self.local_dest.hash
        return None

    # ------------------------------------------------------------------ #
    #  Sending                                                             #
    # ------------------------------------------------------------------ #

    def send_text(self, recipient_hash_hex: str, text: str,
                  on_delivered=None, on_failed=None):
        """
        Send a plain-text message.
        Auto-selects OPPORTUNISTIC for short text, DIRECT for longer.
        recipient_hash_hex: LXMF destination hash as hex string.
        """
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

        msg = LXMF.LXMessage(
            dest,
            self.local_dest,
            text,
            desired_method=method,
        )
        msg.try_propagation_on_fail = True

        if on_delivered:
            msg.register_delivery_callback(lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(lambda m: on_failed(RNS.hexrep(m.hash)))

        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    def send_image(self, recipient_hash_hex: str, image_bytes: bytes,
                   caption: str = "", mime_type: str = "image/jpeg",
                   on_delivered=None, on_failed=None):
        """
        Send an image via FIELD_IMAGE (0x06) using DIRECT delivery.
        image_bytes: raw image bytes (JPEG or PNG).
        """
        recipient_hash = bytes.fromhex(recipient_hash_hex.replace("<","").replace(">","").strip())
        dest = self._resolve_destination(recipient_hash)
        if dest is None:
            if on_failed:
                on_failed(None)
            return None

        # FIELD_IMAGE = 0x06 — image data as [mime_type_bytes, image_bytes]
        fields = {
            LXMF.FIELD_IMAGE: [mime_type.encode("utf-8"), image_bytes],
        }

        msg = LXMF.LXMessage(
            dest,
            self.local_dest,
            caption,                          # caption as message content
            desired_method=LXMF.LXMessage.DIRECT,  # always DIRECT for images
            fields=fields,
        )
        msg.try_propagation_on_fail = True

        if on_delivered:
            msg.register_delivery_callback(lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(lambda m: on_failed(RNS.hexrep(m.hash)))

        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    # ------------------------------------------------------------------ #
    #  Receiving                                                           #
    # ------------------------------------------------------------------ #

    def _on_message_received(self, message):
        """
        Fired by LXMF router on incoming message (background thread).
        Parses text and/or image fields, then calls UI callback.
        """
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

        # Extract image if present
        fields = message.get_fields() if hasattr(message, "get_fields") else {}
        if LXMF.FIELD_IMAGE in fields:
            mime, img_bytes = fields[LXMF.FIELD_IMAGE]
            parsed["image"] = {
                "mime": mime.decode("utf-8") if isinstance(mime, bytes) else mime,
                "data": img_bytes,
            }

        if self.on_message:
            self.on_message(parsed)

    # ------------------------------------------------------------------ #
    #  Path / Destination Resolution                                       #
    # ------------------------------------------------------------------ #

    def _resolve_destination(self, recipient_hash: bytes, timeout: int = 15):
        """
        Recall identity and build destination. Requests path if unknown.
        Returns RNS.Destination or None on timeout.
        """
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
            RNS.log(f"[RNSBackend] Could not resolve identity for {RNS.hexrep(recipient_hash)}", RNS.LOG_WARNING)
            return None

        return RNS.Destination(
            identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            "lxmf",
            "delivery",
        )

    def request_path(self, recipient_hash_hex: str):
        """Manually trigger path discovery (call before sending if needed)."""
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        RNS.Transport.request_path(h)

    # ------------------------------------------------------------------ #
    #  Contacts / Address Book helpers                                     #
    # ------------------------------------------------------------------ #

    def is_known(self, recipient_hash_hex: str) -> bool:
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        return RNS.Identity.recall(h) is not None

    def announce(self):
        """Re-announce our presence on the network."""
        if self.local_dest:
            self.local_dest.announce()
