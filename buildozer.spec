[app]
title = 日语单词本
package.name = japanesevocab
package.domain = com.sanelius2
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0
requirements = python3,kivy==2.3.0,kivymd
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.arch = arm64-v8a
android.logcat_filters = *:S python:D
android.copy_libs = 1
[buildozer]
log_level = 2
warn_on_root = 1
