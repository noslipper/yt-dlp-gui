# yt-dlp 视频下载器

一个基于 **yt-dlp + PySide6 (Qt)** 的现代图形化视频下载工具，支持批量下载、分辨率解析、自动转码、失败重试。Windows 桌面端，界面简洁。

支持站点：YouTube / Bilibili / 抖音 / 优酷 / 爱奇艺 等 yt-dlp 支持的 **2000+ 网站**。

## 功能特性

- 🖥️ 现代化 GUI：PySide6 界面，清爽卡片式布局
- 📥 批量下载：每行一个链接，支持带标题的分享链接自动提取
- 🎯 分辨率解析：一键解析可用清晰度，指定画质下载
- 🎬 编码智能处理：
  - 优先选择 H.264（avc1）视频流，避免非 H.264 容器兼容问题
  - 下载后自动检测编码，非 H.264（如 VP9 / AV1）自动重编码为 H.264 + AAC
- 🎵 音频模式：一键提取并转为 MP3
- 🔄 失败重试：下载失败自动重试，结束后一键「失败重试」只补下失败项
- 📁 文件名模板：标题 / 标题+ID / 日期-标题 / 序号-标题 等预设，可手动修改
- 🔧 自动读取 Windows 系统代理

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python | 3.9+ |
| [PySide6](https://pypi.org/project/PySide6/) | GUI 框架，`pip install PySide6` |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 下载引擎，`pip install -U yt-dlp` |
| ffmpeg | 合并 / 转码 / 音频提取必需（推荐带 libx264 的完整版） |
| deno | （可选）部分站点 JS 解析需要 |

## 安装与运行

### 直接运行源码

```bash
# 1. 安装依赖
pip install PySide6 -U yt-dlp

# 2. 安装 ffmpeg（Windows 可下载完整版，并将 bin 目录加入 PATH）
#    项目内置在发布 exe 中，源码运行需自行安装

# 3. 运行
python ytdlp_gui.py
```

> 提示：应用会自动从系统代理（HKCU 注册表）读取并应用代理，访问 YouTube 等站点前请先开启代理。

### 打包为单文件 exe

使用项目内的 `yt-dlp-GUI.spec`（基于 PyInstaller）：

```bash
pip install pyinstaller
python -m PyInstaller --noconfirm --clean yt-dlp-GUI.spec
```

产物生成在 `dist/yt-dlp-GUI.exe`。

> 打包时需将完整版 `ffmpeg.exe`、`ffprobe.exe`、`deno.exe` 放在项目根目录（spec 会自动打包进 `bin/`）。

## 使用说明

1. **粘贴链接**：在输入框粘贴一个或多个链接（每行一个），或直接粘贴带标题的分享文本，点「粘贴」自动提取 URL
2. **解析分辨率**（可选）：点「解析」查看该视频可用清晰度，选择后按指定画质下载
3. **选择模式**：视频（输出 mp4）或 音频（提取 mp3）
4. **设置保存目录与文件名模板**
5. **开始下载**：进度条实时显示，日志区可查看下载 / 编码 / 转码信息
6. 有链接失败时，按钮变为「失败重试 (N)」，点击仅重下失败项

## 项目结构

```
yt-dlp-gui-release/
├── ytdlp_gui.py          # 主程序（GUI + 下载逻辑）
├── yt-dlp-GUI.spec       # PyInstaller 打包配置
├── icon.ico              # 应用图标
├── icons/                # 按钮图标资源
├── make_icon.py          # 图标生成脚本
├── make_icons.py         # 按钮图标生成脚本
├── _layout2.png          # 界面设计参考
├── _layout_preview.png   # 界面设计参考
└── README.md
```

## 常见问题

**Q：下载报 `HTTP Error 403: Forbidden`？**
这是 YouTube 对视频流 CDN 的间歇性限流（与 IP / 时段相关），程序会自动重试 3 次；若仍失败，点击「失败重试」即可。开启系统代理后成功率更高。

**Q：下载的视频播放不了？**
若原视频流为 VP9 / AV1 编码，程序会自动重编码为 H.264。前提是 ffmpeg 带 libx264 编码器（请勿使用精简版）。

**Q：为什么同一批有的成功有的失败？**
各链接拿到的是不同编码 / 清晰度的流，是否触发限流是独立事件，重试即可。

## License

本项目采用 **GNU General Public License v3.0 (GPL-3.0)**，见 [LICENSE](./LICENSE)。

第三方依赖许可：
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：Unlicense（公域，无限制）
- [PySide6](https://doc.qt.io/qtforpython/)：LGPL-3.0 / GPL-2.0 / GPL-3.0（社区版三选一）
- ffmpeg / ffprobe（随发布版 exe 内嵌）：LGPL / GPL 许可
- deno（随发布版 exe 内嵌）：MIT

> 依据 GPL-3.0，任何对本项目代码的衍生作品必须以 GPL-3.0 开源发布。
