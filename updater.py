# -*- coding: utf-8 -*-
"""
一键更新模块。

流程：检查 GitHub Release → 下载源码 zip → 解压覆盖 → pip install → pyinstaller 打包 → 重启。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
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

# 更新时需要保留的用户文件（不被覆盖）
_PRESERVE_FILES = {"config.json"}


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' → (1, 2, 3)"""
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
    查 GitHub API，返回 None（无更新）或 dict:
    {"version": "1.1.0", "tag": "v1.1.0", "notes": "...", "zip_url": "..."}
    """
    try:
        req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    tag = data.get("tag_name", "")
    if not tag:
        return None

    remote_ver = _parse_version(tag)
    local_ver = _parse_version(current_version)
    if remote_ver <= local_ver:
        return None

    zip_url = data.get("zipball_url", "")
    if not zip_url:
        return None

    return {
        "version": tag.lstrip("vV"),
        "tag": tag,
        "notes": data.get("body", "") or "无更新说明",
        "zip_url": zip_url,
    }


class UpdateWorker(QThread):
    """后台线程执行下载 + 解压 + pip install + pyinstaller。"""
    progress = Signal(str)
    finished_ok = Signal(str)  # 新 exe 路径
    finished_err = Signal(str)  # 错误信息

    def __init__(self, zip_url: str, project_dir: str, spec_name: str = "AsaPet.spec"):
        super().__init__()
        self._zip_url = zip_url
        self._project_dir = project_dir
        self._spec_name = spec_name

    def run(self):
        try:
            self._do_update()
        except Exception as e:
            self.finished_err.emit(str(e))

    def _do_update(self):
        project = self._project_dir

        # 1. 下载 zip
        self.progress.emit("正在下载最新版本...")
        tmp_dir = tempfile.mkdtemp(prefix="asapet_update_")
        zip_path = os.path.join(tmp_dir, "source.zip")
        try:
            urllib.request.urlretrieve(self._zip_url, zip_path)
        except Exception as e:
            raise RuntimeError(f"下载失败: {e}")

        # 2. 解压
        self.progress.emit("正在解压...")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)
        except Exception as e:
            raise RuntimeError(f"解压失败: {e}")

        # GitHub zipball 解压后有一层目录 (Asatsuki0227-AsaPet-xxxxxxx/)
        extracted_dirs = [d for d in os.listdir(tmp_dir)
                         if os.path.isdir(os.path.join(tmp_dir, d))]
        if not extracted_dirs:
            raise RuntimeError("解压后找不到源码目录")
        src_dir = os.path.join(tmp_dir, extracted_dirs[0])

        # 3. 备份用户文件
        self.progress.emit("正在备份配置...")
        backups = {}
        for fname in _PRESERVE_FILES:
            fpath = os.path.join(project, fname)
            if os.path.exists(fpath):
                bak_path = fpath + ".update_bak"
                shutil.copy2(fpath, bak_path)
                backups[fname] = bak_path

        # 4. 覆盖源码文件
        self.progress.emit("正在更新文件...")
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(project, item)
            if item in _PRESERVE_FILES:
                continue
            if item.startswith("."):
                continue
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        # 5. 还原用户文件
        for fname, bak_path in backups.items():
            fpath = os.path.join(project, fname)
            shutil.copy2(bak_path, fpath)
            os.remove(bak_path)

        # 6. pip install
        self.progress.emit("正在安装依赖...")
        req_file = os.path.join(project, "requirements.txt")
        if os.path.exists(req_file):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file, "-q"],
                    cwd=project, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                pass  # 非致命，继续打包

        # 7. pyinstaller 打包
        self.progress.emit("正在打包 EXE（可能需要 30-60 秒）...")
        spec_path = os.path.join(project, self._spec_name)
        if not os.path.exists(spec_path):
            # 找第一个可用的 .spec
            specs = [f for f in os.listdir(project) if f.endswith(".spec")]
            if specs:
                spec_path = os.path.join(project, specs[0])
            else:
                raise RuntimeError("找不到 .spec 文件，无法打包")

        try:
            subprocess.run(
                [sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm"],
                cwd=project, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"打包失败: {e.stderr.decode('utf-8', errors='replace')[-500:]}")

        # 8. 找到新 exe
        dist_dir = os.path.join(project, "dist")
        new_exe = None
        if os.path.isdir(dist_dir):
            for f in os.listdir(dist_dir):
                if f.endswith(".exe"):
                    new_exe = os.path.join(dist_dir, f)
                    break
        if new_exe is None:
            raise RuntimeError("打包完成但找不到生成的 .exe 文件")

        # 清理临时目录
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

        self.progress.emit("更新完成！")
        self.finished_ok.emit(new_exe)


class UpdateDialog(QDialog):
    """更新进度对话框。"""

    def __init__(self, zip_url: str, project_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("正在更新...")
        self.setFixedSize(400, 150)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        self._status_label = QLabel("准备更新...")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self._progress)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self._cancel_btn)

        self._new_exe: Optional[str] = None
        self._worker = UpdateWorker(zip_url, project_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.finished_err.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_success(self, exe_path: str):
        self._new_exe = exe_path
        self.accept()

    def _on_error(self, err: str):
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._status_label.setText("更新失败")
        QMessageBox.critical(self, "更新失败", f"更新过程出错：\n\n{err}")
        self.reject()

    @property
    def new_exe_path(self) -> Optional[str]:
        return self._new_exe
