[app]
title = 日语单词本
package.name = japanesevocab
package.domain = com.sanelius2
source.dir = .
source.include_exts = py,db,ttf
source.include_patterns = jmdict.db,dict_core.py,NotoSansCJK.ttf
version = 2.0.0

# requirements：kivy 完整依赖链
requirements = python3,kivy==2.3.0,sdl2,sdl2_image,sdl2_mixer,sdl2_ttf,pillow,openssl,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True

android.archs = arm64-v8a

android.logcat_filters = *:S python:D
android.copy_libs = 1

# 使用 enable_androidx，避免旧版 support library 冲突
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
