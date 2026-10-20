# -*- coding: utf-8 -*-
"""
动作精简对话框。给 Live2D 模式用——按情绪桶列出当前模型的所有动作，
每个动作带一个"保留"勾选框和一个"试播"按钮，取消勾选等于把这个动作
从 motion_map.json 里删掉，以后情绪桶/AI 选动作都不会再抽到它。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QCheckBox, QPushButton, QDialogButtonBox,
                                QScrollArea, QWidget, QGroupBox, QMessageBox)

_MOOD_LABELS = {
    "happy": "开心", "sad": "难过", "angry": "生气", "shy": "害羞",
    "sleepy": "困倦", "tease": "调皮", "curious": "好奇", "neutral": "中性",
}


class MotionEditorDialog(QDialog):
    """
    传入一个 Live2DRenderer，读它当前的情绪→动作映射展示出来。
    保存时把编辑结果写回 renderer（renderer 自己负责落盘到 motion_map.json）。
    """

    def __init__(self, renderer, parent=None):
        super().__init__(parent)
        self._renderer = renderer
        self.setWindowTitle("动作精简")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(480, 560)

        self._checkboxes: dict[str, list[tuple[str, QCheckBox]]] = {}

        mapping = renderer.get_motion_map()
        if mapping is None:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("模型还没加载完，稍后再试一次吧。"))
            buttons = QDialogButtonBox(QDialogButtonBox.Ok)
            buttons.accepted.connect(self.reject)
            layout.addWidget(buttons)
            return

        hint = QLabel(
            "把看着不对/不想要的动作取消勾选，保存后它们就不会再被随机抽到，"
            "以后接入 AI 自主选动作时也不会出现在可选列表里。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 11px;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for mood, groups in mapping.items():
            if not groups:
                continue
            box = QGroupBox(_MOOD_LABELS.get(mood, mood))
            box_layout = QVBoxLayout(box)
            items = []
            for g in groups:
                row = QHBoxLayout()
                cb = QCheckBox(g)
                cb.setChecked(True)
                play_btn = QPushButton("试播")
                play_btn.setFixedWidth(50)
                play_btn.clicked.connect(lambda _=False, name=g: self._test_play(name))
                row.addWidget(cb, 1)
                row.addWidget(play_btn)
                box_layout.addLayout(row)
                items.append((g, cb))
            self._checkboxes[mood] = items
            scroll_layout.addWidget(box)

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

    def _test_play(self, group: str):
        try:
            self._renderer.test_play(group)
        except Exception as e:
            QMessageBox.warning(self, "试播失败", f"……播放失败了：{e}")

    def _on_save(self):
        new_map = {
            mood: [name for name, cb in items if cb.isChecked()]
            for mood, items in self._checkboxes.items()
        }
        self._renderer.set_motion_map(new_map)
        self.accept()
