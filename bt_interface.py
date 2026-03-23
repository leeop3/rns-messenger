import os

BT_RNODE_CONFIG_TEMPLATE = """
[reticulum]
  enable_transport = False
  share_instance   = True
  shared_instance_port = 37428
  instances_allowed    = 1

[logging]
  loglevel = 4

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

def write_rns_config(config_dir, bt_port="/dev/rfcomm0", frequency=868000000,
                     bandwidth=125000, txpower=14, sf=7, cr=5):
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "config")
    if os.path.exists(config_path):
        return
    config_content = BT_RNODE_CONFIG_TEMPLATE.format(
        bt_port=bt_port, frequency=frequency, bandwidth=bandwidth,
        txpower=txpower, sf=sf, cr=cr,
    )
    with open(config_path, "w") as f:
        f.write(config_content)
    print(f"[BT] Reticulum config written to {config_path}")

def bind_bt_device(device_name):
    try:
        from jnius import autoclass
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return False
        if not adapter.isEnabled():
            return False
        paired = adapter.getBondedDevices().toArray()
        target = None
        for device in paired:
            if device.getName() == device_name:
                target = device
                break
        if target is None:
            return False
        SPP_UUID = autoclass("java.util.UUID").fromString(
            "00001101-0000-1000-8000-00805F9B34FB"
        )
        socket = target.createRfcommSocketToServiceRecord(SPP_UUID)
        socket.connect()
        print(f"[BT] Connected to {device_name}")
        return True
    except Exception as e:
        print(f"[BT] Error: {e}")
        return False

FREQUENCY_PRESETS = {
    "EU868": 868000000,
    "US915": 915000000,
    "AU915": 915000000,
    "AS923": 923000000,
    "IN865": 865000000,
}
