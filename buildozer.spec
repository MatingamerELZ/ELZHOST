[app]

title = ELZ Assistant
package.name = assistant
package.domain = com.elzhots

source.dir = python
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy==2.3.0,pyjnius,android,speech_recognition,pyttsx3,plyer

orientation = portrait
fullscreen = 0

android.permissions =
    RECORD_AUDIO,
    READ_CONTACTS,
    WRITE_CONTACTS,
    CALL_PHONE,
    SEND_SMS,
    RECEIVE_SMS,
    READ_PHONE_STATE,
    WRITE_SETTINGS,
    CHANGE_AUDIO_SETTINGS,
    READ_EXTERNAL_STORAGE,
    WRITE_EXTERNAL_STORAGE,
    INTERNET,
    ACCESS_NETWORK_STATE,
    VIBRATE,
    CAMERA,
    FLASHLIGHT,
    BLUETOOTH,
    BLUETOOTH_ADMIN,
    ACCESS_WIFI_STATE,
    CHANGE_WIFI_STATE

android.minapi = 26
android.ndk_api = 26
android.sdk = 33
android.ndk = 25b
android.arch = arm64-v8a

android.add_src = cpp/voice_processor.cpp,cpp/system_controller.cpp
android.gradle_dependencies = 'androidx.appcompat:appcompat:1.6.1'

android.icon.filename = %(source.dir)s/../assets/icon.png
android.presplash.filename = %(source.dir)s/../assets/presplash.png
android.presplash_color = #0A0A0A

p4a.branch = develop
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
