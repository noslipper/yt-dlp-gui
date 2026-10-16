#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt-dlp GUI 下载器（PySide6 / Qt 版本）
- 现代界面：PySide6 + QSS 美化
- 默认保存目录：用户 Downloads
- 视频统一输出 mp4（webm 等原视频流 remux，不重编码）
- 音频自动提取为 mp3
- 文件名模板：下拉预设 + 可手动修改（默认 %(title)s.%(ext)s）
- URL 支持多行批量下载
- 支持带标题的分享链接（自动提取真实 URL）
- ffmpeg 与应用打包为单个 exe
"""
import os
import re
import subprocess
import sys

import yt_dlp

from PySide6.QtCore import Qt, QThread, Signal, QObject, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QComboBox,
    QProgressBar, QFileDialog, QMessageBox, QFrame,
)

APP_NAME = "yt-dlp 视频下载器"
VERSION = "1.0.3"

# ---------------------------------------------------------------- 工具函数

def resource_path(name):
    """定位打包后（_MEIPASS）或源码目录里的资源。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
    return os.path.join(base, name)


def _icon(name):
    """加载 icons/ 目录下的按钮图标（打包后同样生效）。"""
    p = resource_path(os.path.join("icons", f"{name}.png"))
    if os.path.isfile(p):
        return QIcon(p)
    return QIcon()


def find_ffmpeg():
    """优先使用打包进 exe 的 ffmpeg，否则回退到常见本地路径。"""
    bundled = resource_path(os.path.join("bin", "ffmpeg.exe"))
    if os.path.isfile(bundled):
        return bundled
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "ffmpeg.exe"),
        os.path.join(os.path.expanduser("~"), "Downloads", "ffmpeg", "bin", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def find_deno():
    """优先使用打包进 exe 的 deno（JS 运行时），否则回退到常见本地路径。"""
    bundled = resource_path(os.path.join("bin", "deno.exe"))
    if os.path.isfile(bundled):
        return bundled
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "deno.exe"),
        os.path.join(os.path.expanduser("~"), ".deno", "bin", "deno.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def find_ffprobe():
    """定位 ffprobe（与 ffmpeg 同目录）。"""
    bundled = resource_path(os.path.join("bin", "ffprobe.exe"))
    if os.path.isfile(bundled):
        return bundled
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "ffprobe.exe"),
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


_ffmpeg_encoder_cache = {}


def ffmpeg_supports_encoder(ffmpeg_path, encoder="libx264"):
    """探测指定 ffmpeg 是否编译了某个编码器（缓存结果）。"""
    key = (ffmpeg_path, encoder)
    if key in _ffmpeg_encoder_cache:
        return _ffmpeg_encoder_cache[key]
    ok = False
    try:
        out = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
        )
        ok = encoder in (out.stdout or "")
    except Exception:
        ok = False
    _ffmpeg_encoder_cache[key] = ok
    return ok


def detect_video_codec(path):
    """返回视频流编码名（h264 / vp9 / av1 / hevc ...），探测失败返回 None。"""
    ffprobe = find_ffprobe()
    if not ffprobe or not os.path.isfile(path):
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW,
        )
        return (out.stdout or "").strip() or None
    except Exception:
        return None


def transcode_to_h264(src_path, log_cb):
    """把 src_path 重编码为 H.264 + AAC mp4，原地替换。返回最终路径。"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        log_cb("[转码] 未找到 ffmpeg，跳过自动转 H.264")
        return src_path
    if not ffmpeg_supports_encoder(ffmpeg, "libx264"):
        log_cb("[转码] 当前 ffmpeg 未编译 libx264（精简版），无法重编码视频；"
               "请替换为完整版 ffmpeg。文件保留原编码: " + os.path.basename(src_path))
        return src_path
    base, _ = os.path.splitext(src_path)
    tmp_path = base + ".h264tmp.mp4"
    cmd = [
        ffmpeg, "-y", "-i", src_path,
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        tmp_path,
    ]
    log_cb(f"[转码] 检测到非 H.264 视频流，正在重编码为 H.264: {os.path.basename(src_path)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=_NO_WINDOW)
    except Exception as e:
        log_cb(f"[转码] 启动 ffmpeg 异常: {e}")
        return src_path
    if proc.returncode != 0 or not os.path.isfile(tmp_path):
        log_cb(f"[转码] 失败: {(proc.stderr or '')[-300:]}")
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return src_path
    try:
        os.remove(src_path)
        os.rename(tmp_path, src_path)
        log_cb(f"[转码] 完成 ✓ 已输出 H.264: {os.path.basename(src_path)}")
    except OSError as e:
        log_cb(f"[转码] 替换原文件失败: {e}（保留临时文件 {tmp_path}）")
        return tmp_path
    return src_path


def _detect_system_proxy():
    """读取 Windows 系统代理（HKCU 注册表），返回可用的 http 代理 URL；未启用则返回 None。

    yt-dlp 默认不会自动走系统代理，这里按浏览器同款方式读取后显式传给 yt-dlp，
    否则在开了代理（如访问 YouTube）时仍会直连而触发限流。
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        if not enable:
            return None
        server = (server or "").strip()
        if not server:
            return None
        if "=" in server:  # 形如 http=127.0.0.1:7897;https=... 只取 http 段
            for part in server.split(";"):
                if part.lower().startswith("http="):
                    server = part.split("=", 1)[1]
                    break
        if not server.startswith(("http://", "https://")):
            server = "http://" + server
        return server
    except Exception:
        return None


# 分享链接常见转义：bilibili 等分享链接里的 \u0026 / &amp;
_URL_RE = re.compile(r"https?://[^\s\u3000\uFF01\uFF0C]+", re.IGNORECASE)
_STRIP_TAIL = ".,;:!?)]}\u201d\u2019\uff0c\u3002\uff1b\uff1a\uff01\uff1f\uff09\u3011\u300b"


def extract_urls(text):
    """从可能带标题的多行文本中提取真实 URL 列表，自动去重保序。"""
    urls, seen = [], set()
    for u in _URL_RE.findall(text):
        u = u.rstrip(_STRIP_TAIL)
        u = u.replace("\\u0026", "&").replace("u0026", "&").replace("&amp;", "&")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def default_download_dir():
    return os.path.join(os.path.expanduser("~"), "Downloads")


# 画质预设（可编辑）
FORMAT_PRESETS = {
    "最佳画质（视频+音频，自动合并）": "bestvideo*+bestaudio/best",
    "最高画质（仅视频流）": "bestvideo*",
    "标准画质（单文件）": "best",
}
# 文件名模板预设：中文显示，data 存实际模板字符串
TEMPLATE_PRESETS = [
    ("标题", "%(title)s.%(ext)s"),
    ("标题 + 视频ID", "%(title)s [%(id)s].%(ext)s"),
    ("标题 + 上传者", "%(title)s [%(uploader)s].%(ext)s"),
    ("日期 - 标题", "%(upload_date)s - %(title)s.%(ext)s"),
    ("序号 - 标题", "%(playlist_index)02d - %(title)s.%(ext)s"),
]

# ---------------------------------------------------------------- QSS 主题
QSS = """
* { font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }
QMainWindow, #root { background: #f2f4f8; }

#card {
    background: #ffffff;
    border: 1px solid #e6e9f0;
    border-radius: 14px;
}
#appTitle { font-size: 20px; font-weight: 700; color: #1f2430; }
#appSub { color: #8a91a0; font-size: 12px; }
QLabel { color: #3a4150; }
QLabel[dim="true"] { color: #8a91a0; font-size: 12px; }

QLineEdit, QPlainTextEdit, QComboBox {
    background: #f7f8fc;
    border: 1px solid #e0e4ee;
    border-radius: 9px;
    padding: 8px 10px;
    color: #1f2430;
    font-size: 13px;
    selection-background-color: #ff6b6b;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #ff6b6b;
    background: #ffffff;
}
QPlainTextEdit { font-family: "Consolas", "Microsoft YaHei UI", monospace; }

QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #8a91a0; margin-right: 10px;
}
QComboBox QAbstractItemView {
    background: #ffffff; border: 1px solid #e0e4ee; border-radius: 8px;
    selection-background-color: #ff6b6b; selection-color: #ffffff; padding: 4px;
}

QPushButton {
    border-radius: 9px; padding: 8px 14px; font-size: 13px; font-weight: 600;
}
QPushButton#primary {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff6b6b, stop:1 #c1121f);
    color: #ffffff; border: none;
}
QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff8080, stop:1 #d01824); }
QPushButton#primary:disabled { background: #f0a9ad; }
QPushButton#secondary {
    background: #1f6feb; color: #ffffff; border: none;
}
QPushButton#secondary:hover { background: #3b82f6; }
QPushButton#secondary:disabled { background: #a8c5f0; }
QPushButton#warning {
    background: #f59e0b; color: #ffffff; border: none;
}
QPushButton#warning:hover { background: #fbbf24; color: #1f2430; }
QPushButton#warning:disabled { background: #fcd34d; color: #b9bfcc; }
QPushButton#ghost {
    background: #ffffff; color: #3a4150; border: 1px solid #dde2ec;
}
QPushButton#ghost:hover { background: #f0f3f9; border-color: #ff6b6b; color: #c1121f; }
QPushButton#ghost:disabled { color: #b9bfcc; }

QProgressBar {
    background: #eceff5; border: none; border-radius: 8px; height: 16px; text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff6b6b, stop:1 #c1121f);
    border-radius: 8px;
}
#logBox {
    background: #1e222b; color: #d7dce5; border: none; border-radius: 12px;
    padding: 10px; font-family: "Consolas", "Microsoft YaHei UI", monospace; font-size: 12px;
}
#statusText { font-size: 13px; font-weight: 600; color: #1f2430; }
#extBadge {
    background: #fff1f1; color: #c1121f; border-radius: 8px; padding: 6px 10px; font-weight: 600;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c4cad6; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #aab2c2; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""

# ---------------------------------------------------------------- 下载工作线程
class DownloadWorker(QObject):
    log = Signal(str)
    progress = Signal(int)
    status = Signal(str)
    finished = Signal()

    def __init__(self, urls, opts):
        super().__init__()
        self.urls = urls
        self.opts = opts
        self._stop = False
        self._last_filepath = None
        self.failed_urls = []

    def request_stop(self):
        self._stop = True

    def _hook(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            down = d.get("downloaded_bytes") or 0
            if total:
                self.progress.emit(int(down / total * 100))
        elif d["status"] == "finished":
            self.progress.emit(100)

    def _pp_hook(self, d):
        # 记录最后一个 postprocessor 完成后的最终文件路径
        if d.get("status") == "finished" and d.get("filepath"):
            self._last_filepath = d["filepath"]

    def run(self):
        total = len(self.urls)
        try:
            for idx, url in enumerate(self.urls, 1):
                if self._stop:
                    self.log.emit("[已停止] 用户中断后续任务。")
                    break
                self.status.emit(f"正在下载 第 {idx}/{total} 个")
                self.progress.emit(0)
                self.log.emit(f"\n━━━ 任务 {idx}/{total} ━━━")
                self.log.emit(f"链接: {url}")
                # 在子线程里只做副本；logger 通过信号转发到 GUI 线程，避免跨线程改控件
                opts = dict(self.opts)
                opts["logger"] = _Logger(self.log.emit)
                opts["progress_hooks"] = [self._hook]
                opts["postprocessor_hooks"] = [self._pp_hook]
                self._last_filepath = None
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                    self.log.emit("✓ 下载完成")
                except Exception as e:
                    self.log.emit(f"✗ 失败: {e}")
                    self.failed_urls.append(url)
                    continue
                # 下载后检测视频编码，非 H.264 自动转码
                fp = self._last_filepath
                if fp and os.path.isfile(fp):
                    codec = detect_video_codec(fp)
                    self.log.emit(f"[编码] 视频流编码: {codec or '未知'}")
                    if codec and codec.lower() != "h264":
                        transcode_to_h264(fp, self.log.emit)
        except Exception as e:
            self.log.emit(f"[错误] 下载线程异常: {e}")
        finally:
            self.finished.emit()


class ParseWorker(QObject):
    """后台解析第一个链接，取可用清晰度列表。"""
    log = Signal(str)
    done = Signal(object)     # list[int] 高度列表
    failed = Signal(str)
    finished = Signal()       # run() 无论成败都会发出，用于线程安全收尾

    def __init__(self, url, opts):
        super().__init__()
        self.url = url
        self.opts = opts

    def run(self):
        try:
            opts = dict(self.opts)
            opts["logger"] = _Logger(self.log.emit)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            heights = sorted(
                {f.get("height") for f in (info.get("formats") or []) if f.get("height")},
                reverse=True,
            )
            self.done.emit(heights)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self.finished.emit()


# ---------------------------------------------------------------- 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(880, 720)
        self.setMinimumSize(800, 640)
        ico = resource_path("icon.ico")
        if os.path.isfile(ico):
            self.setWindowIcon(QIcon(ico))

        self.thread = None
        self.worker = None
        self.parse_thread = None
        self.parse_worker = None
        self._res_parsed = False
        self._failed_urls = []
        self._build_ui()
        self._init_state()

    # ---------- UI ----------
    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.setSpacing(12)

        # 头部：保留一行站点说明
        head = QHBoxLayout()
        sub = QLabel("支持 YouTube / Bilibili / 抖音 / 优酷 / 爱奇艺 等 2000+ 站点", objectName="appSub")
        head.addWidget(sub)
        head.addStretch()
        lay.addLayout(head)

        # URL 输入（扁平化：无 label 行，清空/粘贴贴右侧）
        card = QFrame(objectName="card")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(8)
        self.url_edit = QPlainTextEdit()
        self.url_edit.setPlaceholderText(
            "粘贴视频链接，每行一个，支持批量；可直接粘贴带标题的分享链接\n"
            "例如：https://www.youtube.com/watch?v=...  或  https://www.bilibili.com/video/BV..."
        )
        self.url_edit.setFixedHeight(110)
        cl.addWidget(self.url_edit, 1)
        url_btns = QVBoxLayout()
        url_btns.setSpacing(6)
        self.clear_btn = QPushButton("清空", objectName="ghost")
        self.clear_btn.setIcon(_icon("clear"))
        self.clear_btn.clicked.connect(self._clear_urls)
        self.paste_btn = QPushButton("粘贴", objectName="ghost")
        self.paste_btn.setIcon(_icon("paste"))
        self.paste_btn.clicked.connect(self._paste_urls)
        url_btns.addWidget(self.clear_btn)
        url_btns.addWidget(self.paste_btn)
        url_btns.addStretch()
        cl.addLayout(url_btns)
        lay.addWidget(card)

        # 解析 / 分辨率 / 下载模式（单独一行卡片，左右平衡）
        opt_card = QFrame(objectName="card")
        ol = QHBoxLayout(opt_card); ol.setContentsMargins(16, 10, 16, 10); ol.setSpacing(10)
        self.parse_btn = QPushButton("解析", objectName="ghost")
        self.parse_btn.setIcon(_icon("parse"))
        self.parse_btn.clicked.connect(self._parse_formats)
        ol.addWidget(self.parse_btn)
        self.res_combo = QComboBox()
        self.res_combo.addItem("自动（默认）", None)
        self.res_combo.setEnabled(False)
        self.res_combo.setMinimumWidth(130)
        ol.addWidget(self.res_combo)
        ol.addStretch()
        ol.addWidget(QLabel("下载模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["视频（输出 mp4）", "音频（提取 mp3）"])
        self.mode_combo.setFixedWidth(150)
        ol.addWidget(self.mode_combo)
        lay.addWidget(opt_card)

        # 保存目录 + 文件名模板
        dir_card = QFrame(objectName="card")
        dl = QHBoxLayout(dir_card); dl.setContentsMargins(16, 10, 16, 10); dl.setSpacing(8)
        dl.addWidget(QLabel("文件名模板"))
        self.tpl_combo = QComboBox()
        self.tpl_combo.setEditable(True)
        for label, tpl in TEMPLATE_PRESETS:
            self.tpl_combo.addItem(label, tpl)
        self.tpl_combo.setCurrentIndex(0)
        self.tpl_combo.setEditText(self.tpl_combo.currentData())
        self.tpl_combo.currentIndexChanged.connect(self._on_tpl_picked)
        dl.addWidget(self.tpl_combo, 2)
        dl.addSpacing(12)
        dl.addWidget(QLabel("保存目录"))
        self.dir_edit = QLineEdit(default_download_dir())
        dl.addWidget(self.dir_edit, 3)
        self.browse_btn = QPushButton("浏览…", objectName="ghost")
        self.browse_btn.setIcon(_icon("folder"))
        self.browse_btn.clicked.connect(self._choose_dir)
        dl.addWidget(self.browse_btn)
        lay.addWidget(dir_card)

        # 操作按钮行
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.start_btn = QPushButton("开始下载", objectName="primary")
        self.start_btn.setIcon(_icon("start"))
        self.start_btn.clicked.connect(self.start_download)
        self.stop_btn = QPushButton("停止", objectName="ghost")
        self.stop_btn.setIcon(_icon("stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_download)
        self.retry_btn = QPushButton("失败重试", objectName="ghost")
        self.retry_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowBack))
        self.retry_btn.setIconSize(QSize(13, 13))
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self.retry_failed)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.retry_btn)
        btns.addStretch()
        self.open_btn = QPushButton("打开保存目录", objectName="ghost")
        self.open_btn.setIcon(_icon("folder"))
        self.open_btn.clicked.connect(self._open_dir)
        btns.addWidget(self.open_btn)
        lay.addLayout(btns)

        # 进度
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("0%")
        lay.addWidget(self.progress)
        self.status_label = QLabel("就绪", objectName="statusText")
        lay.addWidget(self.status_label)

        # 日志
        log_label = QLabel("下载日志", objectName="appSub")
        lay.addWidget(log_label)
        self.log_view = QPlainTextEdit(objectName="logBox")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        lay.addWidget(self.log_view, 1)

        ff = find_ffmpeg()
        self._log(f"[ffmpeg] {'已就绪: ' + ff if ff else '未找到 ffmpeg，合并/转码将不可用'}")
        self._log(f"[就绪] 默认保存目录: {default_download_dir()}")

    def _init_state(self):
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._on_mode_changed()

    # ---------- 交互 ----------
    def _on_mode_changed(self):
        is_audio = self.mode_combo.currentIndex() == 1
        self.res_combo.setEnabled((not is_audio) and self._res_parsed)

    def _on_tpl_picked(self, idx):
        # 选中预设后，把编辑器内容换成原始模板串（而非中文标签）
        tpl = self.tpl_combo.itemData(idx)
        if tpl:
            self.tpl_combo.setEditText(tpl)

    def _clear_urls(self):
        self.url_edit.clear()
        self._res_parsed = False
        self.res_combo.clear()
        self.res_combo.addItem("自动（默认）", None)
        self.res_combo.setEnabled(False)
        self._log("[清空] 已清空视频地址与解析结果")

    def _paste_urls(self):
        """读取剪贴板，提取 URL 后逐行追加到输入框。"""
        clip = QApplication.clipboard().text()
        urls = extract_urls(clip)
        if not urls:
            QMessageBox.information(self, APP_NAME, "剪贴板中没有可识别的视频链接。")
            return
        existing = self.url_edit.toPlainText()
        seen = set(extract_urls(existing))
        new = [u for u in urls if u not in seen]
        if not new:
            self._log("[粘贴] 剪贴板中的链接均已存在，未重复添加。")
            return
        if existing and not existing.endswith("\n"):
            existing += "\n"
        self.url_edit.setPlainText(existing + "\n".join(new))
        self._log(f"[粘贴] 已添加 {len(new)} 个链接（每行一个）")

    def _parse_formats(self):
        if self.worker is not None:
            QMessageBox.information(self, APP_NAME, "已有下载任务进行中，请先完成或停止。")
            return
        if self.parse_thread is not None:
            QMessageBox.information(self, APP_NAME, "正在解析中，请稍候…")
            return
        urls = extract_urls(self.url_edit.toPlainText())
        if not urls:
            QMessageBox.warning(self, APP_NAME, "未识别到有效的视频链接，请先粘贴。")
            return
        self._log(f"\n[解析] 正在解析（{urls[0]}）…")
        self.status_label.setText("解析中…")
        self.parse_btn.setEnabled(False)
        self.parse_thread = QThread(self)
        self.parse_worker = ParseWorker(urls[0], self._net_opts())
        self.parse_worker.moveToThread(self.parse_thread)
        self.parse_thread.started.connect(self.parse_worker.run)
        self.parse_worker.log.connect(self._log)
        self.parse_worker.done.connect(self._on_parse_done)
        self.parse_worker.failed.connect(self._on_parse_failed)
        # 只靠 finished 触发线程收尾，保证 QThread 真正结束前引用一直存活
        self.parse_worker.finished.connect(self.parse_thread.quit)
        self.parse_worker.finished.connect(self.parse_worker.deleteLater)
        self.parse_thread.finished.connect(self.parse_thread.deleteLater)
        self.parse_thread.finished.connect(self._on_parse_thread_finished)
        self.parse_thread.start()

    def _on_parse_thread_finished(self):
        self.parse_btn.setEnabled(True)
        self.parse_worker = None
        self.parse_thread = None

    def _on_parse_done(self, heights):
        self._res_parsed = True
        self.res_combo.clear()
        self.res_combo.addItem("自动（默认）", None)
        for h in heights:
            self.res_combo.addItem(f"{h}p", h)
        self.res_combo.setCurrentIndex(0)
        if not self.mode_combo.currentIndex() == 1:  # 视频模式
            self.res_combo.setEnabled(True)
        self.status_label.setText(f"解析完成：{len(heights)} 个清晰度可选")
        self._log(f"[解析] 可用清晰度: {', '.join(f'{h}p' for h in heights) if heights else '无'}\n"
                  f"       请选择分辨率后点「开始下载」。")

    def _on_parse_failed(self, err):
        self.status_label.setText("解析失败")
        self._log(f"[解析] 失败: {err}")

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _open_dir(self):
        path = self.dir_edit.text().strip() or default_download_dir()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _log(self, msg):
        # 错误/失败行用红色高亮
        is_err = (
            msg.startswith("✗") or "失败" in msg or "Forbidden" in msg
            or msg.startswith("[错误]") or "ERROR:" in msg
        )
        if is_err:
            safe = (msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            self.log_view.appendHtml(f'<span style="color:#ff6b6b;font-weight:600;">{safe}</span>')
        else:
            self.log_view.appendPlainText(msg)

    def _net_opts(self):
        """供下载与解析共用的网络类基础选项（在 GUI 线程构建）。"""
        opts = {"nocheckcertificate": True}
        ff = find_ffmpeg()
        if ff:
            opts["ffmpeg_location"] = ff
        deno = find_deno()
        if deno:
            opts["js_runtimes"] = {"deno": {"path": deno}}
        proxy = _detect_system_proxy()
        if proxy:
            opts["proxy"] = proxy
        return opts

    def _build_opts(self):
        is_audio = self.mode_combo.currentIndex() == 1
        outdir = self.dir_edit.text().strip() or default_download_dir()
        os.makedirs(outdir, exist_ok=True)
        template = self.tpl_combo.currentData() or self.tpl_combo.currentText().strip() or "%(title)s.%(ext)s"

        opts = {
            "outtmpl": os.path.join(outdir, template),
            "noplaylist": True,
            "restrictfilenames": False,
            "quiet": False,
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 3,
            "sleep_interval": 1,
        }
        opts.update(self._net_opts())

        if is_audio:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            # 优先 avc1(H.264) 视频流 + m4a 音频；拿不到 avc1 再退回 best（可能 vp9/av1，
            # 下载后由 ffprobe 检测并自动重编码为 H.264 兜底）
            res = self.res_combo.currentData()
            if res:
                opts["format"] = (
                    f"bestvideo[vcodec^=avc1][height<={res}]+bestaudio[ext=m4a]/"
                    f"best[vcodec^=avc1][height<={res}]/"
                    f"bestvideo[height<={res}]+bestaudio/best[height<={res}]"
                )
            else:
                opts["format"] = (
                    "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
                    "best[vcodec^=avc1]/"
                    "bestvideo*+bestaudio/best"
                )
            # 目标 mp4：合并时直接 remux 进 mp4；单文件 webm 等也用原视频流转 mp4（不重编码）
            opts["merge_output_format"] = "mp4"
            opts["postprocessors"] = [{
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            }]
        return opts

    def start_download(self):
        if self.worker is not None:
            QMessageBox.information(self, APP_NAME, "已有下载任务进行中，请先停止。")
            return
        text = self.url_edit.toPlainText()
        urls = extract_urls(text)
        if not urls:
            QMessageBox.warning(self, APP_NAME, "未识别到有效的视频链接，请检查输入。")
            return
        if self.dir_edit.text().strip():
            os.makedirs(self.dir_edit.text().strip(), exist_ok=True)
        self._start_worker(urls)

    def retry_failed(self):
        if self.worker is not None:
            QMessageBox.information(self, APP_NAME, "已有下载任务进行中，请先停止。")
            return
        urls = getattr(self, "_failed_urls", []) or []
        if not urls:
            return
        self._log(f"\n[重试] 重新下载 {len(urls)} 个失败链接…")
        self._start_worker(urls)

    def _start_worker(self, urls):
        opts = self._build_opts()
        self._log(f"\n[任务] 共 {len(urls)} 个链接，模式={'音频 mp3' if self.mode_combo.currentIndex()==1 else '视频 mp4'}")
        for u in urls:
            self._log(f"  · {u}")

        self.thread = QThread(self)
        self.worker = DownloadWorker(urls, opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_thread_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.retry_btn.setEnabled(False)
        self.status_label.setText("准备中…")
        self.thread.start()

    def _on_thread_finished(self):
        self.worker = None
        self.thread = None

    def stop_download(self):
        if self.worker:
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            self.status_label.setText("正在停止…")

    def _on_progress(self, pct):
        self.progress.setValue(pct)
        self.progress.setFormat(f"{pct}%")

    def _on_finished(self):
        self.progress.setValue(100)
        self.progress.setFormat("100%")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        # 收集失败链接，启用重试按钮
        failed = list(getattr(self.worker, "failed_urls", []) or []) if self.worker else []
        self._failed_urls = failed
        if failed:
            self.retry_btn.setEnabled(True)
            self.retry_btn.setText(f"失败重试 ({len(failed)})")
            self.status_label.setText(f"完成 ✓ 但有 {len(failed)} 个失败，点「失败重试」重试")
            self._log(f"[汇总] {len(failed)} 个链接失败，可点「失败重试」重新下载。")
        else:
            self.retry_btn.setEnabled(False)
            self.retry_btn.setText("失败重试")
            self.status_label.setText("全部完成 ✓")

    def closeEvent(self, e):
        if self.worker is not None:
            self.worker.request_stop()
            self.thread.quit()
            self.thread.wait(2000)
        if self.parse_worker is not None and self.parse_thread is not None:
            self.parse_thread.quit()
            self.parse_thread.wait(2000)
        e.accept()


class _Logger:
    """把 yt-dlp 日志转发到 GUI 日志区。"""
    def __init__(self, emit):
        self._emit = emit

    def debug(self, msg):
        pass

    def info(self, msg):
        self._emit(msg)

    def warning(self, msg):
        self._emit(f"[警告] {msg}")

    def error(self, msg):
        self._emit(f"[错误] {msg}")


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
