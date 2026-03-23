[app]
title           = RNS Messenger
package.name    = rns_messenger
package.domain  = org.rns

source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,json,cfg,md

version         = 0.1.0

requirements    = python3,kivy==2.2.1,rns,lxmf,pyjnius,msgpack,cryptography,bz2,sqlite3

orientation     = portrait
fullscreen       = 0

android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,ACCESS_NETWORK_STATE

android.api         = 33
android.minapi      = 26
android.ndk         = 25b
android.sdk         = 33
android.ndk_api     = 26
android.archs       = arm64-v8a

android.add_python_libs = _bz2,_sqlite3,_ssl,_hashlib

p4a.bootstrap       = sdl2
p4a.branch          = v2023.02.10

log_level           = 2
warn_on_root        = 1

[buildozer]
log_level           = 2
warn_on_root        = 1
