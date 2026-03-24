import os
import time
import threading
import RNS
import LXMF


def _get_app_dir():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        files_dir = context.getFilesDir().getAbsolutePath()
        return os.path.join(files_dir, "rns_messenger")
    except Exception:
        return os.path.expanduser("~/.rns_messenger")


APP_DIR       = _get_app_dir()
IDENTITY_FILE = os.path.join(APP_DIR, "identity")
LXMF_DIR      = os.path.join(APP_DIR, "lxmf")
RNS_CONFIG    = os.path.join(APP_DIR, "config")

# Match reference: OPPORTUNISTIC only for tiny messages
OPPORTUNISTIC_MAX      = 250
# Match reference: 24-hour resolution timeout
RESOLUTION_TIMEOUT_S   = 24 * 60 * 60
# Match reference: 15-minute check interval
RESOLUTION_INTERVAL_S  = 15 * 60
# Match reference: stagger path requests
PATH_REQUEST_STAGGER_S = 2
# Match reference: 5s startup sweep delay
STARTUP_SWEEP_DELAY_S  = 5


class ContactState:
    PENDING  = "pending"
    ACTIVE   = "active"
    UNRESOLVED = "unresolved"


class RNSBackend:

    def __init__(self):
        self.reticulum       = None
        self.router          = None
        self.identity        = None
        self.local_dest      = None
        self.running         = False

        # Callbacks
        self.on_message      = None
        self.on_state_change = None
        self.on_rns_ready    = None

        # Contact state tracking (hash_hex -> {state, added_ts, public_key})
        self._contacts       = {}
        self._contacts_lock  = threading.Lock()

        os.makedirs(APP_DIR,  exist_ok=True)
        os.makedirs(LXMF_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Startup                                                             #
    # ------------------------------------------------------------------ #

    def start(self):
        self.reticulum = RNS.Reticulum(configdir=RNS_CONFIG)
        self.router = LXMF.LXMRouter(
            storagepath=LXMF_DIR,
            enforce_stamps=False,
        )
        self.identity   = self._load_or_create_identity()
        self.local_dest = self.router.register_delivery_identity(
            self.identity,
            display_name="RNS Messenger",
        )
        self.router.register_delivery_callback(self._on_message_received)
        self.local_dest.announce()
        self.running = True

        # Start background managers (reference pattern)
        threading.Thread(target=self._identity_resolution_loop,
                         daemon=True, name="IdentityResolution").start()
        threading.Thread(target=self._startup_path_sweep,
                         daemon=True, name="StartupPathSweep").start()

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

    def send_text(self, recipient_hash_hex, text,
                  on_delivered=None, on_failed=None):
        recipient_hash = bytes.fromhex(
            recipient_hash_hex.replace("<","").replace(">","").strip())
        dest = self._resolve_destination(recipient_hash)
        if dest is None:
            if on_failed:
                on_failed(None)
            return None

        content_bytes = text.encode("utf-8")
        # Match reference: DIRECT for everything, OPPORTUNISTIC only tiny msgs
        if len(content_bytes) <= OPPORTUNISTIC_MAX:
            method = LXMF.LXMessage.OPPORTUNISTIC
        else:
            method = LXMF.LXMessage.DIRECT

        msg = LXMF.LXMessage(
            dest, self.local_dest, text,
            desired_method=method,
        )
        # Match reference: always fall back to propagation on fail
        msg.try_propagation_on_fail = True

        if on_delivered:
            msg.register_delivery_callback(
                lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(
                lambda m: on_failed(RNS.hexrep(m.hash)))

        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    def send_image(self, recipient_hash_hex, image_bytes, caption="",
                   mime_type="image/jpeg", on_delivered=None, on_failed=None):
        recipient_hash = bytes.fromhex(
            recipient_hash_hex.replace("<","").replace(">","").strip())
        dest = self._resolve_destination(recipient_hash)
        if dest is None:
            if on_failed:
                on_failed(None)
            return None

        fields = {
            LXMF.FIELD_IMAGE: [mime_type.encode("utf-8"), image_bytes],
        }
        # Match reference: always DIRECT for images
        msg = LXMF.LXMessage(
            dest, self.local_dest, caption,
            desired_method=LXMF.LXMessage.DIRECT,
            fields=fields,
        )
        msg.try_propagation_on_fail = True

        if on_delivered:
            msg.register_delivery_callback(
                lambda m: on_delivered(RNS.hexrep(m.hash)))
        if on_failed:
            msg.register_failed_callback(
                lambda m: on_failed(RNS.hexrep(m.hash)))

        self.router.handle_outbound(msg)
        return RNS.hexrep(msg.hash)

    # ------------------------------------------------------------------ #
    #  Receiving                                                           #
    # ------------------------------------------------------------------ #

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
            # Match reference: safe attribute access
            "hops":        getattr(message, "receiving_hops", None),
        }

        fields = message.get_fields() if hasattr(message, "get_fields") else {}
        if LXMF.FIELD_IMAGE in fields:
            mime, img_bytes = fields[LXMF.FIELD_IMAGE]
            parsed["image"] = {
                "mime": mime.decode("utf-8") if isinstance(mime, bytes) else mime,
                "data": img_bytes,
            }

        # Update contact state to ACTIVE when we receive from them
        src = parsed["source_hash"]
        with self._contacts_lock:
            if src in self._contacts:
                self._contacts[src]["state"] = ContactState.ACTIVE

        if self.on_message:
            self.on_message(parsed)

    # ------------------------------------------------------------------ #
    #  Path / Destination Resolution                                       #
    # ------------------------------------------------------------------ #

    def _resolve_destination(self, recipient_hash: bytes,
                              timeout: int = 15):
        """
        Recall identity and build destination.
        Matches reference: request path if not known, wait up to timeout.
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
            print(f"[RNS] Could not resolve {RNS.hexrep(recipient_hash)}")
            return None

        return RNS.Destination(
            identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            "lxmf", "delivery",
        )

    def has_path(self, recipient_hash_hex: str) -> bool:
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        return RNS.Identity.recall(h) is not None

    def request_path(self, recipient_hash_hex: str):
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        RNS.Transport.request_path(h)

    def announce(self):
        """Re-announce. Called on network change (reference pattern)."""
        if self.local_dest:
            self.local_dest.announce()

    # ------------------------------------------------------------------ #
    #  Identity Resolution Loop (reference: IdentityResolutionManager)    #
    # ------------------------------------------------------------------ #

    def _identity_resolution_loop(self):
        """
        Periodically check pending contacts ? matches reference:
        15-minute interval, 24-hour timeout ? UNRESOLVED.
        """
        while self.running:
            try:
                self._check_pending_contacts()
            except Exception as e:
                print(f"[RNS] Resolution loop error: {e}")
            time.sleep(RESOLUTION_INTERVAL_S)

    def _check_pending_contacts(self):
        now = time.time()
        with self._contacts_lock:
            contacts = list(self._contacts.items())

        for hash_hex, info in contacts:
            if info["state"] != ContactState.PENDING:
                continue
            try:
                age = now - info.get("added_ts", now)
                # Match reference: 24-hour timeout ? UNRESOLVED
                if age > RESOLUTION_TIMEOUT_S:
                    print(f"[RNS] {hash_hex[:8]}... timed out ? UNRESOLVED")
                    with self._contacts_lock:
                        self._contacts[hash_hex]["state"] = ContactState.UNRESOLVED
                    continue

                h = bytes.fromhex(hash_hex)
                identity = RNS.Identity.recall(h)
                if identity is not None:
                    print(f"[RNS] {hash_hex[:8]}... resolved ? ACTIVE")
                    with self._contacts_lock:
                        self._contacts[hash_hex]["state"] = ContactState.ACTIVE
                else:
                    # Not in cache ? request path
                    RNS.Transport.request_path(h)
            except Exception as e:
                print(f"[RNS] Resolution error for {hash_hex[:8]}: {e}")

    def _startup_path_sweep(self):
        """
        Match reference: after 5s delay, request paths for all known contacts.
        """
        time.sleep(STARTUP_SWEEP_DELAY_S)
        with self._contacts_lock:
            contacts = list(self._contacts.items())

        print(f"[RNS] Startup sweep: {len(contacts)} contact(s)")
        for hash_hex, info in contacts:
            if info["state"] not in (ContactState.ACTIVE, ContactState.PENDING):
                continue
            try:
                h = bytes.fromhex(hash_hex)
                if RNS.Identity.recall(h) is None:
                    RNS.Transport.request_path(h)
                    print(f"[RNS] Startup sweep: requested path for {hash_hex[:8]}...")
            except Exception as e:
                print(f"[RNS] Startup sweep error: {e}")
            time.sleep(PATH_REQUEST_STAGGER_S)

        print("[RNS] Startup sweep complete")

    # ------------------------------------------------------------------ #
    #  Contact management                                                  #
    # ------------------------------------------------------------------ #

    def add_contact(self, hash_hex: str):
        """Register a contact for identity resolution tracking."""
        hash_hex = hash_hex.strip("<> ").lower()
        with self._contacts_lock:
            if hash_hex not in self._contacts:
                self._contacts[hash_hex] = {
                    "state":    ContactState.PENDING,
                    "added_ts": time.time(),
                }
        # Immediately request path
        try:
            h = bytes.fromhex(hash_hex)
            if RNS.Identity.recall(h) is None:
                RNS.Transport.request_path(h)
        except Exception:
            pass

    def get_contact_state(self, hash_hex: str) -> str:
        hash_hex = hash_hex.strip("<> ").lower()
        with self._contacts_lock:
            return self._contacts.get(hash_hex, {}).get(
                "state", ContactState.PENDING)

    def is_known(self, recipient_hash_hex: str) -> bool:
        h = bytes.fromhex(recipient_hash_hex.strip("<> "))
        return RNS.Identity.recall(h) is not None
