import os
import threading

BT_RNODE_CONFIG_TEMPLATE = """
[reticulum]
  enable_transport = False
  share_instance   = True
  shared_instance_port = 37428
  instances_allowed    = 1

[logging]
  loglevel = 2

[interfaces]

  [[RNode BT Interface]]
    type        = RNodeInterface
    interface_enabled = True
    outgoing    = True

    port        = {bt_port}
    frequency   = {frequency}
    bandwidth   = {bandwidth}
    txpower     = {txpower}
    spreadingfactor = {sf}
    codingrate  = {cr}
    flow_control = False
"""

BT_RNODE_CONFIG_SAFE = """
[reticulum]
  enable_transport = False
  share_instance   = True
  shared_instance_port = 37428
  instances_allowed    = 1

[logging]
  loglevel = 2

[interfaces]

  [[Default Interface]]
    type      = AutoInterface
    interface_enabled = True
"""

# Holds the active BT socket globally so it stays open
_bt_socket = None


def get_paired_devices():
    """
    Returns list of (name, address) tuples for paired BT devices.
    Returns empty list on non-Android or if BT unavailable.
    """
    try:
        from jnius import autoclass
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None or not adapter.isEnabled():
            return []
        paired = adapter.getBondedDevices().toArray()
        return [(d.getName(), d.getAddress()) for d in paired]
    except Exception as e:
        print(f"[BT] get_paired_devices error: {e}")
        return []


def connect_bt_device(device_name):
    """
    Connect to a paired BT device by name using SPP profile.
    Returns (True, port_path) on success or (False, error_message).
    """
    global _bt_socket
    try:
        from jnius import autoclass
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        UUID             = autoclass("java.util.UUID")

        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return False, "No Bluetooth adapter"
        if not adapter.isEnabled():
            return False, "Bluetooth is disabled"

        paired = adapter.getBondedDevices().toArray()
        target = None
        for device in paired:
            if device.getName() == device_name:
                target = device
                break

        if target is None:
            return False, f"Device '{device_name}' not found in paired devices"

        SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        # Close any existing socket
        if _bt_socket is not None:
            try:
                _bt_socket.close()
            except Exception:
                pass

        _bt_socket = target.createRfcommSocketToServiceRecord(SPP_UUID)
        adapter.cancelDiscovery()
        _bt_socket.connect()

        print(f"[BT] Connected to {device_name}")
        return True, "/dev/rfcomm0"

    except Exception as e:
        print(f"[BT] connect error: {e}")
        return False, str(e)


def disconnect_bt():
    global _bt_socket
    if _bt_socket is not None:
        try:
            _bt_socket.close()
        except Exception:
            pass
        _bt_socket = None
    print("[BT] Disconnected")


def is_connected():
    global _bt_socket
    if _bt_socket is None:
        return False
    try:
        return _bt_socket.isConnected()
    except Exception:
        return False


def write_rns_config(config_dir, bt_port="/dev/rfcomm0", frequency=433025000,
                     bandwidth=125000, txpower=17, sf=8, cr=6):
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "config")
    if os.path.exists(config_path):
        return

    try:
        import usbserial4a
        config_content = BT_RNODE_CONFIG_TEMPLATE.format(
            bt_port=bt_port, frequency=frequency, bandwidth=bandwidth,
            txpower=txpower, sf=sf, cr=cr,
        )
        print("[BT] usbserial4a found, using RNode interface")
    except ImportError:
        config_content = BT_RNODE_CONFIG_SAFE
        print("[BT] usbserial4a not found, using AutoInterface fallback")

    with open(config_path, "w") as f:
        f.write(config_content)
    print(f"[BT] Reticulum config written to {config_path}")


FREQUENCY_PRESETS = {
    "433.025 MHz": 433025000,
    "868 MHz":     868000000,
    "915 MHz":     915000000,
    "923 MHz":     923000000,
    "865 MHz":     865000000,
}

BANDWIDTH_PRESETS = {
    "125 kHz":   125000,
    "62.5 kHz":   62500,
    "31.25 kHz":  31250,
}
