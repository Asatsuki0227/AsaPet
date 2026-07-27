# -*- coding: utf-8 -*-
"""
人设编辑对话框。给「直连 API」模式用——整段粘贴 system prompt，原样存进
persona.json，不做拆分/拼接。适合直接搬运已经在别处（比如 AstrBot）调好的长 prompt。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QLabel,
                                QDialogButtonBox)

from ai_chat import load_persona, save_persona, DEFAULT_RAW_PROMPT


class PersonaDialog(QDialog):
    """编辑人设 system prompt，保存到 persona.json。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑人设")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(560, 480)

        persona = load_persona()

        hint = QLabel("把角色的完整 system prompt 粘贴进来（比如你在 AstrBot 里已经写好的那一段）：")

        self._prompt_edit = QTextEdit(persona.get("raw_prompt", DEFAULT_RAW_PROMPT))
        self._prompt_edit.setPlaceholderText("在这里粘贴/编写角色设定……")

        note = QLabel(
            "· 保存后立即生效，下一条消息就会用上新人设。\n"
            "· 这段文字会原样作为 system prompt 发给模型，不会被拆分或改写——"
            "你在里面约定的格式规则（动作括号、称呼规则等）都会照常生效。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self._prompt_edit, 1)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _on_save(self):
        save_persona({"raw_prompt": self._prompt_edit.toPlainText().strip()})
        self.accept()
