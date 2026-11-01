# -*- coding: utf-8 -*-
"""
AsaPet 应用抽屉与快捷启动窗口 (AppDrawerDialog)
提供即时搜索框与可视化列表，展示所有桌面快捷方式与开始菜单应用，支持一键秒开。
"""
from __future__ import annotations

import os
import sys
from typing import Optional, List

from PySide6.QtCore import Qt, QFileInfo, QSize
from PySide6.QtGui import QIcon, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QFileIconProvider, QMessageBox, QWidget
)

from app_launcher import AppLauncher, AppInfo


class AppDrawerDialog(QDialog):
    """应用抽屉对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("应用抽屉 · 快捷启动")
        self.setMinimumSize(420, 520)
        self.resize(460, 560)

        # 窗口标志：置顶、独立工具窗口
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._launcher = AppLauncher.get_instance()
        self._icon_provider = QFileIconProvider()
        self._icon_cache: dict[str, QIcon] = {}

        self._init_ui()
        self._populate_list()

        # 聚焦到输入框
        self._search_input.setFocus()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 顶部说明
        title_label = QLabel("✨ 本地应用与快捷启动")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        desc_label = QLabel("即使隐藏了桌面图标，也能在这里快速找到并一键打开软件。")
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(title_label)
        layout.addWidget(desc_label)

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索应用... (支持拼音、中英文、如 steam, 网易云, code)")
        self._search_input.setFont(QFont("Microsoft YaHei", 10))
        self._search_input.setStyleSheet(
            "QLineEdit { padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fafafa; }"
            "QLineEdit:focus { border: 1px solid #7c83fd; background: #ffffff; }"
        )
        self._search_input.textChanged.connect(self._filter_list)
        self._search_input.returnPressed.connect(self._launch_current)
        layout.addWidget(self._search_input)

        # 应用列表
        self._list_widget = QListWidget()
        self._list_widget.setIconSize(QSize(28, 28))
        self._list_widget.setFont(QFont("Microsoft YaHei", 10))
        self._list_widget.setStyleSheet(
            "QListWidget { border: 1px solid #e0e0e0; border-radius: 6px; padding: 4px; outline: none; }"
            "QListWidget::item { padding: 6px 8px; border-radius: 4px; margin-bottom: 2px; }"
            "QListWidget::item:hover { background-color: #f0f2f5; }"
            "QListWidget::item:selected { background-color: #e8ebff; color: #2b3a8c; font-weight: bold; }"
        )
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget)

        # 底部状态栏与按钮
        bottom_layout = QHBoxLayout()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        bottom_layout.addWidget(self._count_label)
        bottom_layout.addStretch()

        btn_rescan = QPushButton("重新扫描")
        btn_rescan.setToolTip("重新检索桌面和开始菜单中的快捷方式")
        btn_rescan.clicked.connect(self._rescan)
        bottom_layout.addWidget(btn_rescan)

        btn_open = QPushButton("打开 (Enter)")
        btn_open.setDefault(True)
        btn_open.setStyleSheet(
            "QPushButton { background-color: #5c6bc0; color: white; border: none; padding: 6px 14px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4f5cb5; }"
        )
        btn_open.clicked.connect(self._launch_current)
        bottom_layout.addWidget(btn_open)

        layout.addLayout(bottom_layout)

    def _get_icon(self, app: AppInfo) -> QIcon:
        if app.path in self._icon_cache:
            return self._icon_cache[app.path]

        icon = QIcon()
        if os.path.exists(app.path):
            try:
                icon = self._icon_provider.icon(QFileInfo(app.path))
            except Exception:
                pass

        if icon.isNull():
            # 系统图标兜底
            icon = self.style().standardIcon(self.style().StandardPixmap.SP_DesktopIcon)

        self._icon_cache[app.path] = icon
        return icon

    def _populate_list(self):
        self._list_widget.clear()
        apps = self._launcher.get_all_apps()

        for app in apps:
            item = QListWidgetItem()
            item.setText(app.clean_name)
            item.setIcon(self._get_icon(app))
            item.setData(Qt.UserRole, app)
            item.setSizeHint(QSize(0, 42))
            self._list_widget.addItem(item)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

        self._update_count()

    def _filter_list(self, text: str):
        query = text.strip().lower()
        visible_count = 0

        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            app: AppInfo = item.data(Qt.UserRole)
            if not query:
                item.setHidden(False)
                visible_count += 1
            else:
                match = (query in app.clean_name.lower() or
                         query in app.name.lower())
                item.setHidden(not match)
                if match:
                    visible_count += 1

        # 自动选中第一个可见项
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if not item.isHidden():
                self._list_widget.setCurrentItem(item)
                break

        self._update_count(visible_count)

    def _update_count(self, visible: Optional[int] = None):
        total = self._list_widget.count()
        vis = visible if visible is not None else total
        self._count_label.setText(f"显示 {vis} / {total} 个软件")

    def _rescan(self):
        self._launcher.refresh_index()
        self._icon_cache.clear()
        self._populate_list()
        self._filter_list(self._search_input.text())

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._launch_item(item)

    def _launch_current(self):
        item = self._list_widget.currentItem()
        if item and not item.isHidden():
            self._launch_item(item)

    def _launch_item(self, item: QListWidgetItem):
        app: AppInfo = item.data(Qt.UserRole)
        if app:
            ok, msg = self._launcher.launch(app)
            if ok:
                self.accept()
            else:
                QMessageBox.warning(self, "启动失败", f"无法启动该应用：\n{msg}")

    def keyPressEvent(self, event: QKeyEvent):
        # 键盘上下键在输入框中也能移动列表焦点
        if event.key() == Qt.Key_Down:
            cur = self._list_widget.currentRow()
            for r in range(cur + 1, self._list_widget.count()):
                if not self._list_widget.item(r).isHidden():
                    self._list_widget.setCurrentRow(r)
                    break
            event.accept()
            return
        elif event.key() == Qt.Key_Up:
            cur = self._list_widget.currentRow()
            for r in range(cur - 1, -1, -1):
                if not self._list_widget.item(r).isHidden():
                    self._list_widget.setCurrentRow(r)
                    break
            event.accept()
            return
        super().keyPressEvent(event)
