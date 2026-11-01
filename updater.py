# -*- coding: utf-8 -*-
"""
AsaPet 真正的一键无感热更新模块 (True In-App Updater)
无需本地安装 Python / pip / PyInstaller，直接从 GitHub Release 检索并下载
预编译的 Windows 二进制包，解压替换后自动重启，全程仅需数秒。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox, QWidget,
)

GITHUB_REPO = "Asatsuki0227/AsaPet"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# 更新时必须严格保护的用户数据文件（绝不覆盖）
_PRESERVE_FILES = {"config.json", "persona.json", "memory.json", "chat_history.json"}


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' -> (1, 2, 3)"""
    tag = tag.lstrip("vV")
    parts = []
    for p in tag.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_update(current_version: str) -> Optional[dict]:
    """
    检查 GitHub Releases，寻找最新预编译的 Windows Release 资产包。
    返回 None（当前已是最新或无法访问）或 dict:
    {
        "version": "1.5.0",
        "tag": "v1.5.0",
        "notes": "更新日志说明...",
        "download_url": "https://.../AsaPet-v1.5.0-Windows-x64.zip",
        "asset_name": "AsaPet-v1.5.0-Windows-x64.zip"
    }
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AsaPet-Updater"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Updater] check failed: {e}")
        return None

    tag = data.get("tag_name", "")
    if not tag:
        return None

    remote_ver = _parse_version(tag)
    local_ver = _parse_version(current_version)
    if remote_ver <= local_ver:
        return None

    # 从 release assets 中筛选编译好的 Windows 安装包或压缩包
    assets = data.get("assets", [])
    download_url = ""
    asset_name = ""

    for asset in assets:
        name = asset.get("name", "")
        # 优先匹配 AsaPet*.zip 预编译包
        if name.endswith(".zip") and ("asapet" in name.lower() or "windows" in name.lower()):
            download_url = asset.get("browser_download_url", "")
            asset_name = name
            break
        elif name.endswith(".exe") and "asapet" in name.lower():
            download_url = asset.get("browser_download_url", "")
            asset_name = name
            break

    # 兜底：如果 Release 里没上传二进制包，回退到 zipball
    if not download_url:
        download_url = data.get("zipball_url", "")
        asset_name = f"{tag}-source.zip"

    if not download_url:
        return None

    return {
        "version": tag.lstrip("vV"),
        "tag": tag,
        "notes": data.get("body", "") or "无更新说明",
        "download_url": download_url,
        "asset_name": asset_name,
    }


class UpdateWorker(QThread):
    """后台下载预编译二进制包并安全热替换"""
    progress = Signal(str)
    progress_val = Signal(int)    # 0 ~ 100 下载百分比
    finished_ok = Signal(str)     # 新 EXE 路径
    finished_err = Signal(str)    # 错误提示

    def __init__(self, download_url: str, target_dir: str):
        super().__init__()
        self._download_url = download_url
        self._target_dir = target_dir

    def run(self):
        try:
            self._do_update()
        except Exception as e:
            self.finished_err.emit(str(e))

    def _do_update(self):
        self.progress.emit("正在连接更新服务器...")
        tmp_dir = tempfile.mkdtemp(prefix="asapet_dl_")
        dl_path = os.path.join(tmp_dir, "package.bin")

        # 1. 带进度的网络下载
        try:
            def _reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(block_num * block_size * 100 / total_size))
                    self.progress_val.emit(percent)
                    mb_downloaded = (block_num * block_size) / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    self.progress.emit(f"正在下载新版本 ({percent}%) · {mb_downloaded:.1f}/{mb_total:.1f} MB")

            urllib.request.urlretrieve(self._download_url, dl_path, reporthook=_reporthook)
        except Exception as e:
            raise RuntimeError(f"下载更新包失败：{e}")

        self.progress.emit("下载完成，正在解压与校验...")
        self.progress_val.emit(100)

        # 2. 解压与提取二进制文件
        extracted_exe = None
        if zipfile.is_zipfile(dl_path):
            with zipfile.ZipFile(dl_path, "r") as zf:
                zf.extractall(tmp_dir)

            # 在解压出的目录中寻找可执行文件
            for root, _, files in os.walk(tmp_dir):
                for f in files:
                    if f.lower().endswith(".exe") and "asapet" in f.lower():
                        extracted_exe = os.path.join(root, f)
                        break
                if extracted_exe:
                    break

            if not extracted_exe:
                # 寻找任何 exe 文件
                for root, _, files in os.walk(tmp_dir):
                    for f in files:
                        if f.lower().endswith(".exe"):
                            extracted_exe = os.path.join(root, f)
                            break
                    if extracted_exe:
                        break
        elif dl_path.endswith(".exe") or dl_path.endswith(".bin"):
            extracted_exe = dl_path

        if not extracted_exe or not os.path.exists(extracted_exe):
            raise RuntimeError("更新包中未检测到可执行程序 (AsaPet.exe)")

        self.progress.emit("正在安全热替换程序...")

        # 3. 确定当前正在运行的程序位置
        if getattr(sys, "frozen", False):
            current_exe = sys.executable
        else:
            # 如果从源码启动，优先替换 dist/AsaPet.exe 或当前目录的 AsaPet.exe
            dist_exe = os.path.join(self._target_dir, "dist", "AsaPet.exe")
            local_exe = os.path.join(self._target_dir, "AsaPet.exe")
            current_exe = dist_exe if os.path.exists(dist_exe) else local_exe

        target_dir = os.path.dirname(current_exe)
        os.makedirs(target_dir, exist_ok=True)
        target_exe = current_exe

        # 4. Windows NTFS 热重命名替换机制
        # Windows 不允许直接覆写正在运行中的 exe，但允许对其进行重命名
        bak_exe = target_exe + ".old"
        if os.path.exists(bak_exe):
            try:
                os.remove(bak_exe)
            except Exception:
                pass

        if os.path.exists(target_exe):
            try:
                os.replace(target_exe, bak_exe)
            except Exception as e:
                # 如果重命名失败，尝试使用新名称
                target_exe = os.path.join(target_dir, "AsaPet_new.exe")

        # 写入新 EXE
        try:
            shutil.copy2(extracted_exe, target_exe)
        except Exception as e:
            # 还原备份
            if os.path.exists(bak_exe) and not os.path.exists(target_exe):
                try:
                    os.replace(bak_exe, target_exe)
                except Exception:
                    pass
            raise RuntimeError(f"写入新程序文件失败：{e}")

        # 5. 清理临时下载目录
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        self.progress.emit("更新完毕，准备重启！")
        self.finished_ok.emit(target_exe)


class UpdateDialog(QDialog):
    """现代无感更新进度窗口"""

    def __init__(self, download_url: str, target_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("软件自动更新")
        self.setFixedSize(420, 140)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._status_label = QLabel("正在连接服务器...")
        self._status_label.setStyleSheet("font-size: 12px; color: #333;")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            "QProgressBar { border: 1px solid #ccc; border-radius: 4px; text-align: center; height: 18px; }"
            "QProgressBar::chunk { background-color: #5c6bc0; border-radius: 3px; }"
        )
        layout.addWidget(self._progress)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self._cancel_btn)

        self._new_exe: Optional[str] = None
        self._worker = UpdateWorker(download_url, target_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.progress_val.connect(self._progress.setValue)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.finished_err.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_success(self, exe_path: str):
        self._new_exe = exe_path
        self.accept()

    def _on_error(self, err: str):
        QMessageBox.critical(self, "更新失败", f"无法完成自动更新：\n\n{err}")
        self.reject()

    @property
    def new_exe_path(self) -> Optional[str]:
        return self._new_exe
