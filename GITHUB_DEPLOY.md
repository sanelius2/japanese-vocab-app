# 📱 GitHub APK 打包 - 手动操作指南

## 为什么需要手动操作？
GitHub 从 2021 年起不再支持用账号密码直接调用 API，必须使用 **Personal Access Token (PAT)**。
你的账号密码已在对话中暴露，**请立即去 github.com 修改密码并重新生成 Token**。

---

## 第一步：生成 Personal Access Token

1. 登录 [github.com](https://github.com)，点击右上角头像 → **Settings**
2. 左侧菜单最底部 → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. 点击 **Generate new token (classic)**
5. Note 填写：`japanese-vocab-apk`
6. 勾选权限：✅ `repo`（全部）
7. 点击 **Generate token**，复制 token（只显示一次！）

---

## 第二步：在 GitHub 创建仓库

1. 点击 [github.com/new](https://github.com/new)
2. Repository name 填写：`japanese-vocab-app`
3. Description：`日语单词本 Android APK`
4. 选择 **Public**（免费用 Actions）
5. **不要**勾选 Initialize this repository
6. 点击 **Create repository**

---

## 第三步：推送本地代码到 GitHub

在终端中执行（把 `YOUR_TOKEN` 替换为第一步生成的 token）：

```bash
cd /Users/weijunzhang/Desktop/日语单词本/apk

# 添加远程仓库（使用 token 认证）
git remote add origin https://YOUR_TOKEN@github.com/sanelius2/japanese-vocab-app.git

# 推送
git push -u origin main
```

---

## 第四步：触发自动打包

推送成功后，GitHub Actions 会自动开始打包。查看进度：
- 进入仓库页面 → 点击 **Actions** 标签页
- 找到 **Build Android APK** 工作流
- 等待约 **20-40 分钟**（首次较慢，需下载 Android SDK/NDK）

---

## 第五步：下载 APK

打包完成后：
- 在 Actions 工作流页面 → 点击最新一次运行
- 在页面底部 **Artifacts** 区域
- 点击 **japanese-vocab-apk** 下载 zip
- 解压后得到 `.apk` 文件
- 传输到安卓手机，打开安装即可

---

## ⚠️ 安全提醒

你的 GitHub 密码已经出现在对话记录中，**请立即**：
1. 登录 GitHub → Settings → Password → 修改密码
2. 检查账号下是否有异常活动

---

## 文件结构说明

```
apk/
├── main.py                        # Kivy Android 应用主程序
├── buildozer.spec                 # Buildozer 打包配置
└── .github/
    └── workflows/
        └── build_apk.yml          # GitHub Actions 自动打包配置
```
