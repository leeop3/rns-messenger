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

_bt_socket = None


def request_bt_permissions(callback):
    try:
        from android.permissions import request_permissions, Permission, check_permission
        from android import api_version
        if api_version < 31:
            callback(True)
            return
        perms = [Permission.BLUETOOTH_CONNECT, Permission.BLUETOOTH_SCAN]
        if all(check_permission(p) for p in perms):
            callback(True)
            return
        def on_result(permissions, grant_results):
            callback(all(g for g in grant_results))
        request_permissions(perms, on_result)
    except Exception as e:
        print(f"[BT] Permission error: {e}")
        callback(False)


def get_paired_devices():
    results = []
    try:
        from jnius import autoclass
        print("[BT] Scanning for paired devices...")
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return ["No BT adapter"]
        if not adapter.isEnabled():
            return ["BT not enabled - enable BT first"]
        paired_array = adapter.getBondedDevices().toArray()
        print(f"[BT] Found {len(paired_array)} paired device(s)")
        for device in paired_array:
            try:
                name    = device.getName()
                addr    = device.getAddress()
                bt_type = device.getType()
                type_str = {1: "Classic", 2: "BLE", 3: "Dual"}.get(bt_type, str(bt_type))
                print(f"[BT] {name} | {addr} | {type_str}")
                results.append(name)
            except Exception as de:
                print(f"[BT] Device read error: {de}")
        return results if results else ["No paired devices"]
    except Exception as e:
        print(f"[BT] get_paired_devices error: {e}")
        return [f"Error: {str(e)[:30]}"]


def connect_bt_device(device_name):
    global _bt_socket
    try:
        from jnius import autoclass
        print(f"[BT] Connecting to {device_name}...")
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        UUID             = autoclass("java.util.UUID")
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
            return False, f"'{device_name}' not found"
        if target.getType() == 2:
            return False, "BLE only - need Classic"
        if _bt_socket is not None:
            try:
                _bt_socket.close()
            except Exception:
                pass
            _bt_socket = None
        adapter.cancelDiscovery()
        socket = target.createRfcommSocketToServiceRecord(SPP_UUID)
        socket.connect()
        _bt_socket = socket
        print(f"[BT] Connected to {device_name}")
        return True, "/dev/rfcomm0"
    except Exception as e:
        print(f"[BT] connect error: {e}")
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
    # Always write RNode config ? usbserial4a is stubbed in main.py
    config_content = BT_RNODE_CONFIG_TEMPLATE.format(
        bt_port=bt_port, frequency=frequency, bandwidth=bandwidth,
        txpower=txpower, sf=sf, cr=cr,
    )
    with open(config_path, "w") as f:
        f.write(config_content)
    print(f"[BT] RNode config written to {config_path}")


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
