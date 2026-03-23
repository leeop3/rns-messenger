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

_bt_socket = None


def get_paired_devices():
    """
    Returns list of device name strings for paired BT Classic devices.
    Must be called from a background thread on Android.
    """
    results = []
    try:
        from jnius import autoclass, cast
        print("[BT] Scanning for paired devices...")

        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        BluetoothDevice  = autoclass("android.bluetooth.BluetoothDevice")

        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            print("[BT] ERROR: No Bluetooth adapter found")
            return ["No BT adapter"]

        if not adapter.isEnabled():
            print("[BT] ERROR: Bluetooth is not enabled")
            return ["BT not enabled"]

        paired_set = adapter.getBondedDevices()
        if paired_set is None:
            print("[BT] No paired devices set returned")
            return ["No paired devices"]

        paired_array = paired_set.toArray()
        print(f"[BT] Found {len(paired_array)} paired device(s)")

        for device in paired_array:
            try:
                name = device.getName()
                addr = device.getAddress()
                # BT Classic check ? type 1=Classic, 2=BLE, 3=Dual
                bt_type = device.getType()
                type_str = {1: "Classic", 2: "BLE", 3: "Dual"}.get(bt_type, f"Unknown({bt_type})")
                print(f"[BT] Device: {name} | {addr} | {type_str}")
                results.append(name)
            except Exception as de:
                print(f"[BT] Error reading device: {de}")

        if not results:
            return ["No paired devices"]
        return results

    except Exception as e:
        print(f"[BT] get_paired_devices error: {e}")
        import traceback
        traceback.print_exc()
        return [f"Error: {str(e)[:30]}"]


def connect_bt_device(device_name):
    """
    Connect to paired BT Classic device by name using SPP UUID.
    Returns (True, port) or (False, error_message).
    """
    global _bt_socket
    try:
        from jnius import autoclass
        print(f"[BT] Connecting to {device_name} via BT Classic SPP...")

        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        UUID             = autoclass("java.util.UUID")

        # Standard SPP (Serial Port Profile) UUID ? BT Classic only
        SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return False, "No Bluetooth adapter"
        if not adapter.isEnabled():
            return False, "Bluetooth not enabled"

        paired = adapter.getBondedDevices().toArray()
        target = None
        for device in paired:
            if device.getName() == device_name:
                target = device
                break

        if target is None:
            return False, f"'{device_name}' not found in paired devices"

        bt_type = target.getType()
        print(f"[BT] Device type: {bt_type} (1=Classic 2=BLE 3=Dual)")
        if bt_type == 2:
            return False, "Device is BLE only ? need BT Classic"

        # Close existing socket
        if _bt_socket is not None:
            try:
                _bt_socket.close()
            except Exception:
                pass
            _bt_socket = None

        # Stop discovery before connecting (important!)
        adapter.cancelDiscovery()

        # Create BT Classic RFCOMM socket
        socket = target.createRfcommSocketToServiceRecord(SPP_UUID)
        print("[BT] Connecting RFCOMM socket...")
        socket.connect()
        _bt_socket = socket
        print(f"[BT] Connected to {device_name}")
        return True, "/dev/rfcomm0"

    except Exception as e:
        print(f"[BT] connect error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)[:60]


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
