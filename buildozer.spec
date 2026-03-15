[app]
title = 日语单词本
package.name = japanesevocab
package.domain = com.sanelius2
source.dir = .
source.include_exts = py,db
source.include_patterns = jmdict.db,dict_core.py
version = 2.0.0

# requirements：kivy 完整依赖链，不能省略
requirements = python3,kivy==2.3.0,kivymd,sdl2,pillow,openssl

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True

# 修复：旧版用 android.arch，新版必须用 android.archs
android.archs = arm64-v8a

android.logcat_filters = *:S python:D
android.copy_libs = 1

[buildozer]
log_level = 2
warn_on_root = 1
