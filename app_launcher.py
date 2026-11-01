# -*- coding: utf-8 -*-
"""
AsaPet 应用扫描与启动器 (AppLauncher)
用于在 Windows 系统中扫描桌面快捷方式、开始菜单及系统工具，
支持语义别名映射、模糊匹配与一键无感启动。
"""
from __future__ import annotations

import os
import re
import sys
import time
import subprocess
from typing import Optional, Tuple, List, Dict

# 忽略无用快捷方式关键词（小写）
_IGNORE_KEYWORDS = (
    "卸载", "uninstall", "remove", "setup", "install",
    "help", "readme", "read me", "license", "许可",
    "crash", "report", "feedback", "manual", "手册",
    "website", "网页", "配置工具", "configurator", "updater",
    "repair", "修复"
)

# 常见系统命令与协议别名映射
_SYSTEM_ALIAS_MAP: Dict[str, str] = {
    "计算器": "calc",
    "calc": "calc",
    "记事本": "notepad",
    "notepad": "notepad",
    "画图": "mspaint",
    "mspaint": "mspaint",
    "任务管理器": "taskmgr",
    "taskmgr": "taskmgr",
    "资源管理器": "explorer",
    "我的电脑": "explorer",
    "此电脑": "explorer",
    "文件管理器": "explorer",
    "系统设置": "ms-settings:",
    "设置": "ms-settings:",
    "控制面板": "control",
    "命令行": "cmd",
    "cmd": "cmd",
    "终端": "wt",
    "powershell": "powershell",
    "注册表": "regedit",
}

# 意图/语义别名映射（用户口语 -> 常见软件候选关键词，按优先级排布）
_SEMANTIC_ALIASES: Dict[str, List[str]] = {
    "听歌": ["网易云音乐", "cloudmusic", "qq音乐", "qqmusic", "kugou", "酷狗", "spotify", "music"],
    "放歌": ["网易云音乐", "cloudmusic", "qq音乐", "qqmusic", "spotify", "music"],
    "音乐": ["网易云音乐", "cloudmusic", "qq音乐", "qqmusic", "spotify", "music"],
    "网易云": ["网易云音乐", "cloudmusic"],
    "qq音乐": ["qq音乐", "qqmusic"],
    "游戏": ["steam", "wegame", "epic games", "genshin", "starrail"],
    "玩游戏": ["steam", "wegame", "epic games"],
    "steam": ["steam"],
    "写代码": ["visual studio code", "vscode", "code", "pycharm", "cursor", "idea", "sublime"],
    "代码": ["visual studio code", "vscode", "code", "pycharm", "cursor"],
    "vscode": ["visual studio code", "vscode", "code"],
    "浏览器": ["microsoft edge", "google chrome", "chrome", "firefox", "brave", "edge"],
    "上网": ["microsoft edge", "google chrome", "chrome", "firefox", "edge"],
    "网页": ["microsoft edge", "google chrome", "chrome", "firefox", "edge"],
    "edge": ["microsoft edge", "edge"],
    "chrome": ["google chrome", "chrome"],
    "微信": ["wechat", "微信"],
    "qq": ["qq"],
}


class AppInfo:
    """应用信息载体"""
    def __init__(self, name: str, path: str, is_system: bool = False):
        self.name = name                      # 原始显示名
        self.path = path                      # 目标路径或命令
        self.is_system = is_system            # 是否为系统内置命令
        self.clean_name = self._clean(name)   # 清洗后的标准应用名

    @staticmethod
    def _clean(raw: str) -> str:
        s = raw.replace(" - 快捷方式", "").replace(" - Shortcut", "")
        s = re.sub(r"\.lnk$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\.url$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\.exe$", "", s, flags=re.IGNORECASE)
        return s.strip()

    def __repr__(self):
        return f"<AppInfo {self.clean_name} -> {self.path}>"


class AppLauncher:
    """本地应用索引与启动器单例"""
    _instance: Optional[AppLauncher] = None

    @classmethod
    def get_instance(cls) -> AppLauncher:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._apps: List[AppInfo] = []
        self._last_scan_time = 0.0
        self._scan_interval = 300.0  # 5 分钟自动更新
        self.refresh_index()

    def get_scan_directories(self) -> List[str]:
        dirs = [
            os.path.expanduser('~/Desktop'),
            'C:/Users/Public/Desktop',
            os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs'),
            os.path.expandvars(r'%ProgramData%\Microsoft\Windows\Start Menu\Programs'),
        ]
        return [d for d in dirs if os.path.exists(d)]

    def refresh_index(self):
        """扫描桌面与开始菜单中的所有有效快捷方式与系统工具"""
        found_apps: Dict[str, AppInfo] = {}

        # 1. 扫描快捷方式
        for d in self.get_scan_directories():
            for root, _, files in os.walk(d):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ('.lnk', '.url'):
                        full_path = os.path.join(root, f)
                        base_name = os.path.splitext(f)[0]
                        clean_name = AppInfo._clean(base_name)
                        lower_name = clean_name.lower()

                        if any(kw in lower_name for kw in _IGNORE_KEYWORDS):
                            continue

                        # 优先保留桌面快捷方式
                        if clean_name not in found_apps or 'Desktop' in root:
                            found_apps[clean_name] = AppInfo(clean_name, full_path)

        # 2. 系统应用与协议
        for alias, cmd in _SYSTEM_ALIAS_MAP.items():
            if alias not in found_apps:
                found_apps[alias] = AppInfo(alias, cmd, is_system=True)

        # 按系统应用在后、字母排序在前组织
        self._apps = sorted(
            found_apps.values(),
            key=lambda a: (a.is_system, a.clean_name.lower())
        )
        self._last_scan_time = time.time()
        print(f"[AppLauncher] 索引就绪：共找到 {len(self._apps)} 个可用软件/工具。")

    def get_all_apps(self) -> List[AppInfo]:
        if time.time() - self._last_scan_time > self._scan_interval:
            self.refresh_index()
        return list(self._apps)

    def find_app(self, query: str) -> Optional[AppInfo]:
        """
        智能识别用户输入，找到最匹配的应用程序对象。
        """
        if not query or not query.strip():
            return None

        # 去除开头祈使词和结尾冗余词
        q = query.strip()
        q = re.sub(r"^(请|帮我|麻烦|麻烦帮我)?(打开|启动|运行|开一下|开下|开启|唤起|进入|去|玩|听)\s*", "", q).strip()
        q = re.sub(r"(软件|应用|程序|客户端|一下|下)$", "", q).strip()
        if not q:
            q = query.strip()

        q_lower = q.lower()
        all_apps = self.get_all_apps()

        # 1. 语义别名匹配
        candidate_keywords = []
        for intent, target_keywords in _SEMANTIC_ALIASES.items():
            if intent == q_lower or intent in q_lower or q_lower in intent:
                candidate_keywords.extend(target_keywords)

        if candidate_keywords:
            for kw in candidate_keywords:
                kw_lower = kw.lower()
                for app in all_apps:
                    app_lower = app.clean_name.lower()
                    if kw_lower == app_lower or kw_lower in app_lower:
                        return app

        # 2. 精确全称匹配（去空格）
        q_condensed = re.sub(r"\s+", "", q_lower)
        for app in all_apps:
            app_condensed = re.sub(r"\s+", "", app.clean_name.lower())
            if q_condensed == app_condensed:
                return app

        # 3. 打分式模糊搜索
        best_app = None
        best_score = 0

        for app in all_apps:
            app_lower = app.clean_name.lower()
            score = 0

            if q_lower in app_lower:
                if app_lower.startswith(q_lower):
                    score = 100 - len(app_lower)
                else:
                    score = 70 - len(app_lower)
            elif app_lower in q_lower:
                score = 60 + len(app_lower)

            if score > best_score:
                best_score = score
                best_app = app

        return best_app

    def launch(self, app_or_path: AppInfo | str) -> Tuple[bool, str]:
        """
        启动应用或快捷方式。
        返回 (success, 提示信息或应用名)
        """
        if isinstance(app_or_path, AppInfo):
            target = app_or_path.path
            name = app_or_path.clean_name
        else:
            target = str(app_or_path)
            name = os.path.basename(target)

        try:
            os.startfile(target)
            return True, name
        except FileNotFoundError:
            try:
                subprocess.Popen(target, shell=True)
                return True, name
            except Exception as e2:
                return False, f"未找到可执行程序: {e2}"
        except Exception as e:
            # 尝试通过 cmd /c start
            try:
                subprocess.Popen(f'start "" "{target}"', shell=True)
                return True, name
            except Exception as e3:
                return False, f"启动异常: {e}"

    def find_and_launch(self, query: str) -> Tuple[bool, str]:
        """组合查找并启动"""
        app = self.find_app(query)
        if not app:
            return False, f"未在电脑中找到匹配「{query}」的软件快捷方式"
        ok, msg = self.launch(app)
        if ok:
            return True, app.clean_name
        return False, msg


# 标签提取工具函数
_OPEN_TAG_RE = re.compile(r"\[open:\s*(.+?)\s*\]", re.IGNORECASE)


def parse_open_tag(text: str) -> Tuple[Optional[str], str]:
    """
    从文本中提取 [open:xxx] 标签。
    返回 (app_keyword_or_None, 去掉标签后的纯文本)
    """
    m = _OPEN_TAG_RE.search(text)
    if m:
        app_kw = m.group(1).strip()
        clean = text[:m.start()] + text[m.end():]
        return app_kw, clean.strip()
    return None, text
