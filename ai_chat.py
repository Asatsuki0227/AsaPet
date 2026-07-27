# -*- coding: utf-8 -*-
"""
直连 AI API 对话客户端。

跟 desktop_pet.py 里的 OneBotClient 是平级的两条路：AstrBot 走 WebSocket，
这里直接用任意 OpenAI 兼容接口（DeepSeek / Kimi / 智谱 / SiliconFlow / OpenAI 官方等）。
接口对齐 OneBotClient（同名方法 send_user_message / send_poke_event / connected /
update_config），desktop_pet.py 里两条路可以共用同一批调用点。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# 历史记录最多保留的对话轮数（一轮 = 一条 user + 一条 assistant）
MAX_HISTORY_TURNS = 10

# 没有 persona.json 或用户还没填时的兜底 system prompt
DEFAULT_RAW_PROMPT = (
    "你正在扮演一个陪伴在用户身边的桌面宠物角色，性格温柔、话不多。"
    "请始终用第一人称回复，保持角色感，不要提及你是 AI 或语言模型。"
)


def persona_path() -> str:
    if hasattr(sys, "_MEIPASS"):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "persona.json")


def load_persona() -> dict:
    """
    人设就是一段完整的 system prompt（原样传给 LLM，不做任何拼接/注入）。
    这样可以直接把已经在别处（比如 AstrBot）调好的长 prompt 整段搬过来用。
    """
    path = persona_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("raw_prompt", "").strip():
                return data
        except Exception as e:
            print(f"[Persona] load error: {e}")
    return {"raw_prompt": DEFAULT_RAW_PROMPT}


def save_persona(persona: dict):
    path = persona_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(persona, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Persona] save error: {e}")


def request_models(manager: QNetworkAccessManager, base_url: str, api_key: str) -> QNetworkReply:
    """
    发起 GET {base_url}/models（OpenAI 兼容接口的标准列表端点）。
    返回 QNetworkReply，调用方自己连 finished 信号，再用 parse_models_response 解析。
    """
    url = QUrl(f"{base_url.strip().rstrip('/')}/models")
    req = QNetworkRequest(url)
    if api_key:
        req.setRawHeader(b"Authorization", f"Bearer {api_key.strip()}".encode("utf-8"))
    return manager.get(req)


def parse_models_response(reply: QNetworkReply) -> tuple[list[str], str]:
    """返回 (模型 id 列表, 错误信息)。成功时错误信息为空串；失败时列表为空。"""
    if reply.error() != QNetworkReply.NoError:
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        return [], f"获取失败（{status or ''} {reply.errorString()}）"

    raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        items = data.get("data", [])
        ids = sorted({item.get("id", "") for item in items if item.get("id")})
    except Exception as e:
        return [], f"返回内容解析失败：{e}"

    if not ids:
        return [], "没有获取到任何模型，该服务商可能不支持模型列表接口"
    return ids, ""


def build_system_prompt(persona: dict) -> str:
    """
    人设就是用户自己写好的一整段 prompt，原样传给 LLM，不做任何拼接/改写。
    不强加情绪标签之类的格式要求——用户的 prompt 里可能已经约定了自己的
    动作/语气标注方式（比如「(动作)对话」），硬塞进去反而会冲突。
    """
    return persona.get("raw_prompt", "").strip() or DEFAULT_RAW_PROMPT


class DirectAIClient(QObject):
    """
    直连 OpenAI 兼容 Chat Completions 接口。

    没有长连接、没有心跳——每次发消息就是一次独立的 HTTPS POST。
    """
    reply_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._manager = QNetworkAccessManager(self)
        self._history: list[dict] = []  # [{"role": "user"/"assistant", "content": "..."}]
        self._persona = load_persona()
        self._pending_replies: list[QNetworkReply] = []  # 保活引用，避免被 GC

    # ---- 跟 OneBotClient 对齐的接口 ----
    @property
    def connected(self) -> bool:
        """直连模式没有"连接状态"，用 api_key 是否已配置来代表"可用"。"""
        return bool(self._config.get("api_key", "").strip())

    def start(self):
        pass  # 直连模式不需要预先建立连接

    def stop(self):
        pass

    def update_config(self, config: dict):
        self._config = config
        self._persona = load_persona()

    def reload_persona(self):
        """人设编辑对话框保存后调用，让下一条消息用上新人设。"""
        self._persona = load_persona()

    def send_user_message(self, text: str) -> bool:
        if not self.connected:
            return False
        self._dispatch(text)
        return True

    def send_poke_event(self) -> bool:
        if not self.connected:
            return False
        self._dispatch("[系统提示]对方戳了戳你，请做出一个简短、符合人设的反应。", record_as_user=False)
        return True

    # ---- 内部实现 ----
    def _dispatch(self, text: str, record_as_user: bool = True):
        base_url = self._config.get("api_base_url", "").strip().rstrip("/")
        api_key = self._config.get("api_key", "").strip()
        model = self._config.get("api_model", "").strip()
        if not base_url or not model:
            self.error_occurred.emit("……API 地址或模型名还没填呢，去设置里填一下吧。")
            return

        system_prompt = build_system_prompt(self._persona)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._history[-(MAX_HISTORY_TURNS * 2):])
        messages.append({"role": "user", "content": text})

        body = json.dumps({
            "model": model,
            "messages": messages,
        }).encode("utf-8")

        url = QUrl(f"{base_url}/chat/completions")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        req.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))

        reply = self._manager.post(req, body)
        self._pending_replies.append(reply)
        reply.finished.connect(lambda: self._on_finished(reply, text, record_as_user))

    def _on_finished(self, reply: QNetworkReply, sent_text: str, record_as_user: bool):
        if reply in self._pending_replies:
            self._pending_replies.remove(reply)

        if reply.error() != QNetworkReply.NoError:
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            detail = reply.errorString()
            reply.deleteLater()
            self.error_occurred.emit(f"……请求失败了（{status or ''} {detail}）。")
            return

        raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()
        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            self.error_occurred.emit(f"……返回的内容有点奇怪，解析失败了：{e}")
            return

        if record_as_user:
            self._history.append({"role": "user", "content": sent_text})
        self._history.append({"role": "assistant", "content": content})
        # 历史太长就砍掉最老的，只留最近 N 轮
        max_len = MAX_HISTORY_TURNS * 2
        if len(self._history) > max_len:
            self._history = self._history[-max_len:]

        self.reply_received.emit(content)
