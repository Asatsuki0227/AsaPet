# -*- coding: utf-8 -*-
"""
记忆与历史管理对话框。
供「直连 API」模式查看和编辑：
1. 长期记忆（已记住的关于用户的事实列表、用户称呼、手动增删改）
2. 最近的对话历史（查看记录、一键清空上下文）
"""
from __future__ import annotations

import time
from typing import Optional, Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTextEdit,
    QTabWidget, QWidget, QMessageBox, QInputDialog, QCheckBox,
    QDialogButtonBox
)
from ai_chat import (
    load_memory, save_memory, load_chat_history, save_chat_history
)


class MemoryDialog(QDialog):
    """
    记忆与对话历史管理窗口。
    """

    def __init__(self, ai_client, config: dict, save_cb: Optional[Callable[[dict], None]] = None, parent=None):
        super().__init__(parent)
        self._client = ai_client
        self._config = dict(config)
        self._save_cb = save_cb
        self._memory = load_memory()
        self._history = load_chat_history()

        self.setWindowTitle("记忆与历史管理")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(600, 520)

        # 根布局
        root_layout = QVBoxLayout(self)

        # 顶部说明
        header = QLabel("记忆与对话历史管理")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        sub = QLabel("宵崎奏记住了关于你的这些事情。她会在对话中自然地关心你，像长期相处的朋友一样。")
        sub.setStyleSheet("color: #666; font-size: 11px;")
        sub.setWordWrap(True)
        root_layout.addWidget(header)
        root_layout.addWidget(sub)

        # 分页 Tab
        self._tabs = QTabWidget(self)
        self._init_memory_tab()
        self._init_history_tab()
        root_layout.addWidget(self._tabs, 1)

        # 底部按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    # -------------------- Tab 1: 长期记忆 --------------------
    def _init_memory_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 称呼行
        nick_row = QHBoxLayout()
        nick_lbl = QLabel("你的称呼 / 昵称：")
        self._nick_edit = QLineEdit(self._memory.get("user_nickname", "") or self._config.get("nickname", "诶嘿"))
        self._nick_edit.setPlaceholderText("在对话中奏对你的称呼（如：诶嘿、老师、制作人）")
        nick_row.addWidget(nick_lbl)
        nick_row.addWidget(self._nick_edit, 1)
        layout.addLayout(nick_row)

        # 事实列表标题与计数
        self._facts_title = QLabel("已记住的事实与偏好：")
        layout.addWidget(self._facts_title)

        # 列表控件
        self._facts_list = QListWidget()
        self._refresh_facts_list()
        layout.addWidget(self._facts_list, 1)

        # 操作按钮
        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋ 添加记忆")
        add_btn.clicked.connect(self._add_fact)
        edit_btn = QPushButton("✎ 编辑选中")
        edit_btn.clicked.connect(self._edit_fact)
        del_btn = QPushButton("🗑 删除选中")
        del_btn.clicked.connect(self._delete_fact)
        clear_btn = QPushButton("清空所有记忆")
        clear_btn.setStyleSheet("color: #d9534f;")
        clear_btn.clicked.connect(self._clear_all_facts)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # 自动提取开关
        self._auto_memory_cb = QCheckBox("启用对话自动记忆（在日常聊天中自动提炼你的喜好与近况）")
        self._auto_memory_cb.setChecked(self._config.get("auto_memory", True))
        layout.addWidget(self._auto_memory_cb)

        self._tabs.addTab(tab, "长期事实记忆")

    def _refresh_facts_list(self):
        self._facts_list.clear()
        facts = self._memory.get("facts", [])
        for f in facts:
            item = QListWidgetItem(f)
            self._facts_list.addItem(item)
        self._facts_title.setText(f"已记住的事实与偏好（共 {len(facts)} 条）：")

    def _add_fact(self):
        text, ok = QInputDialog.getText(
            self, "添加记忆", "输入奏应该记住的关于你的事实（如喜好、习惯、日常）：",
            QLineEdit.Normal, ""
        )
        if ok and text.strip():
            fact = text.strip()
            self._memory.setdefault("facts", []).append(fact)
            self._refresh_facts_list()
            self._facts_list.setCurrentRow(self._facts_list.count() - 1)

    def _edit_fact(self):
        row = self._facts_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在列表中选中一条要编辑的记忆。")
            return
        curr_text = self._facts_list.item(row).text()
        text, ok = QInputDialog.getText(
            self, "编辑记忆", "修改记忆内容：",
            QLineEdit.Normal, curr_text
        )
        if ok and text.strip():
            self._memory["facts"][row] = text.strip()
            self._refresh_facts_list()
            self._facts_list.setCurrentRow(row)

    def _delete_fact(self):
        row = self._facts_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在列表中选中一条要删除的记忆。")
            return
        del self._memory["facts"][row]
        self._refresh_facts_list()

    def _clear_all_facts(self):
        if not self._memory.get("facts"):
            return
        reply = QMessageBox.question(
            self, "清空记忆确认",
            "确定要清空全部长期事实记忆吗？\n清空后奏将忘记所有了解到的关于你的个人信息与习惯。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._memory["facts"] = []
            self._refresh_facts_list()

    # -------------------- Tab 2: 对话历史 --------------------
    def _init_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        note = QLabel("最近对话历史（本地保留最近 60 条交互，用于维持近期聊天上下文）：")
        note.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(note)

        self._history_text = QTextEdit()
        self._history_text.setReadOnly(True)
        self._refresh_history_text()
        layout.addWidget(self._history_text, 1)

        bottom_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新记录")
        refresh_btn.clicked.connect(self._refresh_history_from_disk)
        clear_hist_btn = QPushButton("清空对话上下文")
        clear_hist_btn.setStyleSheet("color: #d9534f;")
        clear_hist_btn.clicked.connect(self._clear_history)

        bottom_row.addWidget(refresh_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(clear_hist_btn)
        layout.addLayout(bottom_row)

        self._tabs.addTab(tab, "对话上下文历史")

    def _refresh_history_from_disk(self):
        self._history = load_chat_history()
        self._refresh_history_text()

    def _refresh_history_text(self):
        if not self._history:
            self._history_text.setHtml("<p style='color: #888;'>（暂无对话历史）</p>")
            return

        html_parts = ["<div style='font-family: sans-serif; line-height: 1.5;'>"]
        for item in self._history:
            role = item.get("role", "")
            content = item.get("content", "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            time_str = item.get("time", "")
            time_badge = f"<span style='color: #999; font-size: 10px;'>[{time_str}]</span> " if time_str else ""

            if role == "user":
                html_parts.append(
                    f"<p style='margin: 4px 0;'>{time_badge}"
                    f"<b style='color: #2563eb;'>你：</b>"
                    f"<span style='color: #222;'>{content}</span></p>"
                )
            else:
                html_parts.append(
                    f"<p style='margin: 4px 0 8px 0;'>{time_badge}"
                    f"<b style='color: #7c3aed;'>奏：</b>"
                    f"<span style='color: #333;'>{content}</span></p>"
                )
        html_parts.append("</div>")
        self._history_text.setHtml("".join(html_parts))

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "清空对话历史",
            "确定要清空当前的对话上下文吗？\n这会让奏开始一个全新的话题，不会影响已记住的事实。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._history.clear()
            save_chat_history([])
            if hasattr(self._client, "clear_history"):
                self._client.clear_history()
            self._refresh_history_text()

    # -------------------- 保存与同步 --------------------
    def _on_save(self):
        # 1. 保存长期记忆
        nick = self._nick_edit.text().strip() or "诶嘿"
        facts = [self._facts_list.item(i).text().strip() for i in range(self._facts_list.count()) if self._facts_list.item(i).text().strip()]
        self._memory["user_nickname"] = nick
        self._memory["facts"] = facts
        self._memory["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_memory(self._memory)

        # 2. 同步配置中的 nickname 与 auto_memory
        self._config["nickname"] = nick
        self._config["auto_memory"] = self._auto_memory_cb.isChecked()
        if self._save_cb:
            self._save_cb(self._config)

        # 3. 通知客户端重载
        if hasattr(self._client, "reload_memory"):
            self._client.reload_memory()
        if hasattr(self._client, "update_config"):
            self._client.update_config(self._config)

        self.accept()
