# -*- coding: utf-8 -*-
"""
直连 AI API 对话客户端与本地记忆管理系统。

功能特性：
1. 直连任意 OpenAI 兼容接口（DeepSeek / Kimi / 智谱 / SiliconFlow / OpenAI 官方等）。
2. 本地持久化对话历史（chat_history.json），重启程序后仍可维持近期上下文。
3. 本地持久化长期记忆（memory.json）：记录用户称呼与事实/偏好，自然注入系统人设。
4. 异步自动提炼记忆：在日常聊天中自动从对话中提炼关于用户的新事实，无需中断或阻塞交互。
5. 独立模型自主选动作：配合 Live2D 动作库实现灵动的神态反应。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# 每次发给 LLM 的历史记录最多保留轮数（一轮 = 一条 user + 一条 assistant）
MAX_HISTORY_TURNS = 10

# 本地持久化保留的最大对话条数（供记忆管理对话框查看历史）
MAX_PERSISTED_HISTORY = 60

# 长期记忆最大保留条数
MAX_FACTS_COUNT = 50

# 没有 persona.json 或用户还没填时的兜底 system prompt
DEFAULT_RAW_PROMPT = (
    "你正在扮演一个陪伴在用户身边的桌面宠物角色，性格温柔、话不多。"
    "请始终用第一人称回复，保持角色感，不要提及你是 AI 或语言模型。"
)


def _base_dir() -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def persona_path() -> str:
    return os.path.join(_base_dir(), "persona.json")


def memory_path() -> str:
    return os.path.join(_base_dir(), "memory.json")


def chat_history_path() -> str:
    return os.path.join(_base_dir(), "chat_history.json")


# -------------------- 人设加载与保存 --------------------
def load_persona() -> dict:
    """
    人设就是一段完整的 system prompt（原样传给 LLM）。
    可以直接把已经在别处（比如 AstrBot）调好的长 prompt 整段搬过来用。
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


# -------------------- 长期记忆与对话历史存储 --------------------
def load_memory() -> dict:
    """加载长期记忆（用户称呼、记住的事实列表、更新时间）。"""
    path = memory_path()
    default_mem = {
        "user_nickname": "",
        "facts": [],
        "updated_at": "",
    }
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {
                    "user_nickname": str(data.get("user_nickname", "")),
                    "facts": [str(x) for x in data.get("facts", []) if isinstance(x, (str, int, float))],
                    "updated_at": str(data.get("updated_at", "")),
                }
        except Exception as e:
            print(f"[Memory] load error: {e}")
    return default_mem


def save_memory(mem: dict):
    """保存长期记忆到 memory.json。"""
    path = memory_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Memory] save error: {e}")


def load_chat_history() -> list[dict]:
    """加载最近对话历史记录。"""
    path = chat_history_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                valid = []
                for item in data:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        valid.append({
                            "role": str(item["role"]),
                            "content": str(item["content"]),
                            "time": str(item.get("time", "")),
                        })
                return valid
        except Exception as e:
            print(f"[ChatHistory] load error: {e}")
    return []


def save_chat_history(history: list[dict]):
    """持久化保存最近对话历史到 chat_history.json。"""
    path = chat_history_path()
    try:
        to_save = history[-MAX_PERSISTED_HISTORY:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ChatHistory] save error: {e}")


# -------------------- 模型列表端点工具 --------------------
def request_models(manager: QNetworkAccessManager, base_url: str, api_key: str) -> QNetworkReply:
    url = QUrl(f"{base_url.strip().rstrip('/')}/models")
    req = QNetworkRequest(url)
    if api_key:
        req.setRawHeader(b"Authorization", f"Bearer {api_key.strip()}".encode("utf-8"))
    return manager.get(req)


def parse_models_response(reply: QNetworkReply) -> tuple[list[str], str]:
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


# -------------------- 组合 System Prompt --------------------
def build_system_prompt(persona: dict, memory: Optional[dict] = None) -> str:
    """
    将人设 System Prompt 与本地长期记忆（称呼、已知事实）自然拼接。
    保持人设主体的完整性，同时赋予角色对用户的长期记忆。
    """
    base = persona.get("raw_prompt", "").strip() or DEFAULT_RAW_PROMPT
    if not memory:
        return base

    nickname = memory.get("user_nickname", "").strip()
    facts = [f.strip() for f in memory.get("facts", []) if isinstance(f, str) and f.strip()]

    if not nickname and not facts:
        return base

    sections = [base, "\n\n---\n【关于用户的长期记忆】"]
    if nickname:
        sections.append(f"- 用户称呼：{nickname}")
    if facts:
        sections.append("- 你了解到的关于用户的事实与生活近况：")
        for f in facts:
            sections.append(f"  · {f}")
    sections.append("【指引】这些是你与用户长期相处中记住的事情。请像熟悉的朋友一样，在适当时机自然体现对这些事情的关心，切勿生硬罗列或刻意背诵上述事实。")
    return "\n".join(sections)


# -------------------- 直连 AI 客户端 --------------------
class DirectAIClient(QObject):
    """
    直连 OpenAI 兼容 Chat Completions 接口，集成上下文历史与长期记忆。
    """
    reply_received = Signal(str)
    error_occurred = Signal(str)
    motion_requested = Signal(str)
    memory_updated = Signal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._manager = QNetworkAccessManager(self)
        self._history: list[dict] = load_chat_history()
        self._persona = load_persona()
        self._memory = load_memory()
        self._pending_replies: list[QNetworkReply] = []
        self._available_actions: list[str] = []

        # 若记忆中尚未设置称呼，则同步配置中的 nickname
        cfg_nick = self._config.get("nickname", "").strip()
        if cfg_nick and not self._memory.get("user_nickname"):
            self._memory["user_nickname"] = cfg_nick
            save_memory(self._memory)

    # ---- 对齐 OneBotClient 接口 ----
    @property
    def connected(self) -> bool:
        return bool(self._config.get("api_key", "").strip())

    def start(self):
        pass

    def stop(self):
        pass

    def update_config(self, config: dict):
        self._config = config
        self._persona = load_persona()
        self._memory = load_memory()
        cfg_nick = self._config.get("nickname", "").strip()
        if cfg_nick and not self._memory.get("user_nickname"):
            self._memory["user_nickname"] = cfg_nick
            save_memory(self._memory)

    def reload_persona(self):
        self._persona = load_persona()

    def reload_memory(self):
        self._memory = load_memory()
        self.memory_updated.emit()

    def get_memory(self) -> dict:
        return dict(self._memory)

    def get_history(self) -> list[dict]:
        return list(self._history)

    def clear_history(self):
        """清空最近对话上下文。"""
        self._history.clear()
        save_chat_history([])

    def clear_memory(self):
        """清空所有长期事实记忆。"""
        self._memory = {
            "user_nickname": self._config.get("nickname", ""),
            "facts": [],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_memory(self._memory)
        self.memory_updated.emit()

    def set_available_actions(self, names: list[str]):
        self._available_actions = list(names)

    def send_user_message(self, text: str) -> bool:
        if not self.connected:
            return False
        # 如果是系统主动搭话提示词，不作为真实用户发言计入记忆提取与用户显示
        is_sys_prompt = text.startswith("[系统提示]")
        self._dispatch(text, record_as_user=not is_sys_prompt)
        return True

    def send_poke_event(self) -> bool:
        if not self.connected:
            return False
        self._dispatch("[系统提示]对方戳了戳你，请做出一个简短、符合人设的反应。", record_as_user=False)
        return True

    # ---- 内部请求调度 ----
    def _dispatch(self, text: str, record_as_user: bool = True):
        base_url = self._config.get("api_base_url", "").strip().rstrip("/")
        api_key = self._config.get("api_key", "").strip()
        model = self._config.get("api_model", "").strip()
        if not base_url or not model:
            self.error_occurred.emit("……API 地址或模型名还没填呢，去设置里填一下吧。")
            return

        system_prompt = build_system_prompt(self._persona, self._memory)

        # 组装上下文消息（过滤掉本地扩展字段，仅保留 role 与 content）
        messages = [{"role": "system", "content": system_prompt}]
        for item in self._history[-(MAX_HISTORY_TURNS * 2):]:
            messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": text})

        payload = {
            "model": model,
            "messages": messages,
        }
        reply = self._post_chat(base_url, api_key, payload)
        reply.finished.connect(lambda: self._on_finished(reply, text, record_as_user))

    def _post_chat(self, base_url: str, api_key: str, payload: dict) -> QNetworkReply:
        url = QUrl(f"{base_url}/chat/completions")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        if api_key:
            req.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))
        body = json.dumps(payload).encode("utf-8")
        reply = self._manager.post(req, body)
        self._pending_replies.append(reply)
        return reply

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
            content = (data["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            self.error_occurred.emit(f"……返回的内容有点奇怪，解析失败了：{e}")
            return

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        if record_as_user:
            self._history.append({"role": "user", "content": sent_text, "time": now_str})
        self._history.append({"role": "assistant", "content": content, "time": now_str})

        # 保持持久化与内存中的历史长度
        save_chat_history(self._history)
        if len(self._history) > MAX_PERSISTED_HISTORY:
            self._history = self._history[-MAX_PERSISTED_HISTORY:]

        self.reply_received.emit(content)

        # 1. 触发自主选动作
        if content and self._available_actions and self._config.get("ai_motion_picking", False):
            self._pick_motion(content)

        # 2. 触发记忆自动提取（若开启且是真实用户发言）
        if record_as_user and content and self._config.get("auto_memory", True):
            self._extract_memory(sent_text, content)

    # ---- 长期记忆自动提炼 ----
    def _extract_memory(self, sent_text: str, reply_text: str):
        # 极短词（如“好”、“嗯”、“1”）无需提炼
        clean_user = sent_text.strip()
        if len(clean_user) <= 2:
            return

        base_url = (self._config.get("motion_api_base_url", "").strip()
                    or self._config.get("api_base_url", "").strip()).rstrip("/")
        api_key = (self._config.get("motion_api_key", "").strip()
                   or self._config.get("api_key", "").strip())
        model = (self._config.get("motion_api_model", "").strip()
                 or self._config.get("api_model", "").strip())
        if not base_url or not model:
            return

        existing_facts = self._memory.get("facts", [])
        existing_str = "\n".join(f"- {f}" for f in existing_facts[-15:]) if existing_facts else "（暂无）"

        prompt = (
            "你是一个记忆提炼助手。请分析以下用户与桌宠角色的简短对话，提炼出关于用户的新的重要个人信息/事实"
            "（例如：称呼/名字、喜好、作息习惯、现实生活状态、重要日程、情绪困扰等）。\n\n"
            f"已记录的事实：\n{existing_str}\n\n"
            f"当前对话：\n用户：{clean_user}\n角色：{reply_text}\n\n"
            "任务要求：\n"
            "1. 仅提炼用户主动透露的关于用户自身的新信息，忽略日常问候、角色的台词或泛泛闲聊；\n"
            "2. 若有新事实，输出为一个纯 JSON 字符串数组，例如：[\"喜欢吃抹茶冰淇淋\", \"下周要参加考试\"]，每条事实不超过20字，必须准确、客观、简短；\n"
            "3. 若无任何新的个人事实，只输出：无\n"
            "严禁输出任何多余分析或解释，仅输出 JSON 数组或“无”。"
        )
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 150,
        }
        reply = self._post_chat(base_url, api_key, payload)
        reply.finished.connect(lambda: self._on_memory_extracted(reply))

    def _on_memory_extracted(self, reply: QNetworkReply):
        if reply in self._pending_replies:
            self._pending_replies.remove(reply)

        if reply.error() != QNetworkReply.NoError:
            reply.deleteLater()
            return

        raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()
        try:
            data = json.loads(raw)
            result = (data["choices"][0]["message"].get("content") or "").strip()
        except Exception:
            return

        # 剔除推理模型的思考链
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        if not result or (len(result) < 6 and "无" in result):
            return

        new_facts = []
        try:
            m = re.search(r"\[.*?\]", result, flags=re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list):
                    new_facts = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        if not new_facts:
            for line in result.splitlines():
                cleaned = line.strip(" -*0123456789.、\"'[]")
                if cleaned and len(cleaned) <= 30:
                    new_facts.append(cleaned)

        if not new_facts:
            return

        existing = set(self._memory.get("facts", []))
        added = False
        for fact in new_facts:
            fact = fact.strip("，。,. ")
            if fact and fact not in existing and len(fact) <= 40:
                self._memory.setdefault("facts", []).append(fact)
                existing.add(fact)
                added = True
                print(f"[Memory] 学习到新记忆: {fact}")

        if added:
            if len(self._memory["facts"]) > MAX_FACTS_COUNT:
                self._memory["facts"] = self._memory["facts"][-MAX_FACTS_COUNT:]
            self._memory["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_memory(self._memory)
            self.memory_updated.emit()

    # ---- AI 自主选动作 ----
    def _pick_motion(self, reply_text: str):
        base_url = (self._config.get("motion_api_base_url", "").strip()
                    or self._config.get("api_base_url", "").strip()).rstrip("/")
        api_key = (self._config.get("motion_api_key", "").strip()
                   or self._config.get("api_key", "").strip())
        model = (self._config.get("motion_api_model", "").strip()
                 or self._config.get("api_model", "").strip())
        if not base_url or not model:
            return

        actions = self._available_actions
        prompt = (
            "下面是一句对话回复和一份可选的动作名列表。请选出最符合这句话语气/情绪的"
            "一个动作，只输出动作名本身，不要输出任何其他文字、标点或解释；"
            "如果没有合适的，只输出：无\n\n"
            f"动作列表：\n{chr(10).join(actions)}\n\n"
            f"这句回复：{reply_text}"
        )
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 60,
        }
        reply = self._post_chat(base_url, api_key, payload)
        reply.finished.connect(lambda: self._on_motion_picked(reply))

    def _on_motion_picked(self, reply: QNetworkReply):
        if reply in self._pending_replies:
            self._pending_replies.remove(reply)

        if reply.error() != QNetworkReply.NoError:
            print(f"[DirectAIClient] motion pick failed: {reply.errorString()}")
            reply.deleteLater()
            return

        raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()
        try:
            data = json.loads(raw)
            action = (data["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            print(f"[DirectAIClient] motion pick parse failed: {e}")
            return

        action = re.sub(r"<think>.*?</think>", "", action, flags=re.DOTALL).strip()
        action = action.strip("。.，,\"'`\n ")
        if action and action in self._available_actions:
            self.motion_requested.emit(action)
