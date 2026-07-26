# -*- coding: utf-8 -*-
"""
角色载体切换对话框。让用户在「图片」和「Live2D」之间挑，并选文件路径。
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                QRadioButton, QLineEdit, QPushButton,
                                QDialogButtonBox, QFileDialog, QLabel,
                                QButtonGroup, QWidget)


class CharacterDialog(QDialog):
    """
    返回值：(mode, image_path, live2d_path)
    - mode ∈ {"image", "live2d"}
    - image_path 是当前配置里的图片路径，可能是用户选的绝对路径也可能保持原样
    - live2d_path 是模型 .model3.json 的绝对路径
    """

    def __init__(self, current_mode: str, image_path: str,
                 live2d_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("切换角色")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(520, 240)

        self._radio_image = QRadioButton("图片模式（透明 PNG）")
        self._radio_live2d = QRadioButton("Live2D 模式（.model3.json）")
        group = QButtonGroup(self)
        group.addButton(self._radio_image)
        group.addButton(self._radio_live2d)
        if current_mode == "live2d":
            self._radio_live2d.setChecked(True)
        else:
            self._radio_image.setChecked(True)

        self._image_edit = QLineEdit(image_path)
        self._image_edit.setPlaceholderText("留空则使用内置 1.png")
        image_pick = QPushButton("浏览…")
        image_pick.clicked.connect(self._pick_image)

        self._live2d_edit = QLineEdit(live2d_path)
        self._live2d_edit.setPlaceholderText("选择 xxx.model3.json 文件")
        live2d_pick = QPushButton("浏览…")
        live2d_pick.clicked.connect(self._pick_live2d)

        image_row = QHBoxLayout()
        image_row.addWidget(self._image_edit, 1)
        image_row.addWidget(image_pick)

        live2d_row = QHBoxLayout()
        live2d_row.addWidget(self._live2d_edit, 1)
        live2d_row.addWidget(live2d_pick)

        form = QFormLayout()
        form.addRow(self._radio_image)
        form.addRow("图片路径", image_row)
        form.addRow(self._radio_live2d)
        form.addRow("模型 JSON", live2d_row)

        note = QLabel(
            "· Live2D 模式需要先安装 live2d-py（pip install live2d-py，Python ≥ 3.11）。\n"
            "· 请自备 Cubism 3+ 模型（.moc3 + .model3.json），仓库不包含任何第三方模型。\n"
            "· 商用请遵守 Live2D Cubism SDK 授权条款。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _pick_image(self):
        start_dir = os.path.dirname(self._image_edit.text()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", start_dir, "图片 (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._image_edit.setText(path)
            self._radio_image.setChecked(True)

    def _pick_live2d(self):
        start_dir = os.path.dirname(self._live2d_edit.text()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Live2D 模型", start_dir,
            "Live2D 模型 (*.model3.json)"
        )
        if path:
            self._live2d_edit.setText(path)
            self._radio_live2d.setChecked(True)

    def _on_accept(self):
        if self._radio_live2d.isChecked():
            path = self._live2d_edit.text().strip()
            if not path or not os.path.exists(path):
                # 用户选了 Live2D 但没给合法路径——不关闭对话框
                self._live2d_edit.setFocus()
                self._live2d_edit.selectAll()
                return
        self.accept()

    def result_value(self) -> tuple[str, str, str]:
        mode = "live2d" if self._radio_live2d.isChecked() else "image"
        return mode, self._image_edit.text().strip(), self._live2d_edit.text().strip()
