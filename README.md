# 纽约时报最受欢迎文章 (中英对照版)

这个项目包含一个 Python 脚本，可以从纽约时报中文网抓取最受欢迎的文章列表，并生成一个 HTML 文件，点击其中的链接会直接进入中英双语阅读模式。

## iPhone App

项目现已包含一个原生 SwiftUI iPhone 应用，位于 [`iOS/`](iOS/)。在 macOS 的完整 Xcode 中打开 `iOS/NYTimesReader.xcodeproj`，选择签名团队后即可运行到 iPhone 或模拟器。更新后可在根目录运行 `./iOS/NYTimesReader/update_iphone.sh`，自动构建并安装到已配对的 iPhone。它离线打包全部归档文章，并提供搜索、收藏以及中英/字体阅读设置；详细说明见 [`iOS/README.md`](iOS/README.md)。

根目录是网页、抓取器和 iOS 离线资源的唯一维护入口；`NYTimes/` 是历史独立副本，仅作保留，不再同步维护。

## 如何使用

1.  **安装依赖:**

    首先，你需要安装项目所需的 Python 库。在你的终端或命令行中运行以下命令：

    ```bash
    pip install -r requirements.txt
    ```

2.  **运行脚本:**

    安装完依赖后，运行 `scraper.py` 脚本来生成网页：

    ```bash
    python scraper.py
    ```

    脚本会生成一个名为 `index.html` 的文件。

3.  **查看结果:**

    在项目目录运行 `python3 -m http.server 8000`，然后在浏览器打开 `http://localhost:8000/`。文章列表会通过 HTTP 缓存加载，点击任意文章即可进入中英文对照阅读。
