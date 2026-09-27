# 双语新闻 iPhone App

这是基于原项目离线文章库的原生 SwiftUI iPhone 应用（iOS 17+）。它会将 `articles.json` 和 `articles/` 作为应用资源打包，因此首次安装后不需要网络也能阅读已归档文章。

## 在 Xcode 中运行

1. 用 Xcode 打开 `NYTimesReader.xcodeproj`。
2. 在 Target 的 **Signing & Capabilities** 中选择你的 Apple Development Team；如 Bundle Identifier 冲突，可改成自己的唯一标识。
3. 选择 iPhone 模拟器或已连接的 iPhone，按 Run（⌘R）。

## 已实现功能

- 按日期浏览 1,119 篇文章，支持中英文标题搜索。
- 文章内中英对照、仅英文、仅中文阅读。
- 原生工具栏调节字号和字体，偏好会保存在本机。
- 收藏、单词本和搜索记录会同时保存到 `UserDefaults` 和 App 沙盒中的 `Documents/user-data.json`，升级时会自动合并恢复。
- 收藏与取消收藏（左滑文章或阅读页按钮），收藏跨启动和升级保存。
- 原文章中的外链会在 Safari 中打开。

> 首次编译需复制约 34 MB 的离线文章资源，属于正常情况。

## 一键更新并安装到 iPhone

在项目根目录运行：

```bash
./iOS/NYTimesReader/update_iphone.sh
```

脚本会自动递增版本号（例如 `1.0.1`、`1.0.2`，构建号同步递增），构建 IPA，通过 Xcode 直接安装到已配对的 `iPhone`，并在设备已解锁时启动 App。安装前会备份收藏、单词本和偏好设置，安装后自动恢复；版本只在安装成功后写回，失败不会占用新版本号。若设备名称不是 `iPhone`，可传入 `DEVICE_NAME="设备名称"`；若有重名设备，可传入 `DEVICE_ID`。

## 使用 AltServer / AltStore 安装

1. 在 Mac 上运行 AltServer，并确认 iPhone 与 Mac 处于同一网络。
2. 在 Xcode 的 **Accounts** 中登录 Apple ID，并选择要使用的开发 Team。
3. 在 `iOS` 目录运行 `TEAM_ID=你的TeamID NYTimesReader/build_ipa.sh`；未传入时会使用脚本原有 Team。
4. 脚本成功后会在桌面生成 `双语头条.ipa`。
5. 按住 AltServer 菜单图标，选择 **Install IPA**，选中该文件并在 AltStore 中完成安装。

免费 Apple ID 的证书通常 7 天过期，需要在有效期内用 AltStore 刷新；付费 Apple Developer Program 账号可延长有效期。
