[app]
title           = RNS Messenger
package.name    = rns_messenger
package.domain  = org.rns

source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,json,cfg,md

version         = 0.1.0

requirements    = python3,kivy==2.3.0,rns,lxmf,pyjnius,msgpack,cryptography

orientation     = portrait
fullscreen      = 0

android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,ACCESS_NETWORK_STATE

android.api         = 33
android.minapi      = 26
android.ndk         = 25b
android.sdk         = 33
android.ndk_api     = 26
android.archs       = arm64-v8a, armeabi-v7a

p4a.bootstrap       = sdl2
p4a.branch          = release-2024.01.21

log_level           = 2
warn_on_root        = 1

[buildozer]
log_level           = 2
warn_on_root        = 1
