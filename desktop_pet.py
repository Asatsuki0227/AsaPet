# -*- coding: utf-8 -*-
"""
Kanade 桌面宠物
- 无边框、透明、始终置顶
- 左键拖动
- 单击轮流触发：跳跃 / 压扁回弹 / 左右抖动
- 互动时随机气泡（不遮挡角色）
- 右键菜单：调整大小 / 置顶开关 / 退出
- 鼠标滚轮缩放
"""
import sys
import os
import json
import time
import random
from typing import Optional

from PySide6.QtCore import (Qt, QTimer, QPoint, QPointF, QRect, QSize, QUrl,
                            QElapsedTimer, Signal,
                            QPropertyAnimation, QEasingCurve,
                            QParallelAnimationGroup, QSequentialAnimationGroup,
                            Property, QObject)
from PySide6.QtGui import (QPixmap, QPainter, QAction, QCursor, QFont,
                           QColor, QPainterPath, QBrush, QPen, QIcon,
                           QFontMetrics, QSurfaceFormat)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QMenu,
                               QSystemTrayIcon, QLineEdit, QVBoxLayout,
                               QInputDialog, QMessageBox, QDialog,
                               QFormLayout, QDialogButtonBox, QPushButton)
from PySide6.QtNetwork import QHostAddress, QNetworkRequest
from PySide6.QtWebSockets import QWebSocketServer, QWebSocket

from pet_renderer import (make_renderer, ImageRenderer, PetRenderer,
                          LIVE2D_AVAILABLE)
from character_dialog import CharacterDialog
from updater import check_for_update, UpdateDialog


# --------------------------- 配置区 ---------------------------
VERSION = "1.1.0"
IMAGE_FILE = "1.png"
DEFAULT_HEIGHT = 260        # 默认宠物高度（像素）
MIN_HEIGHT = 120
MAX_HEIGHT = 800
WHEEL_STEP = 20             # 滚轮每次缩放像素
BUBBLE_DURATION_MS = 2200   # 气泡显示时间

# 待机动画配置
IDLE_TRIGGER_MS = 3 * 60 * 1000     # 无交互多久后开始播放待机动作（3 分钟）
IDLE_INTERVAL_MIN_MS = 45 * 1000    # 待机动作之间的最小间隔
IDLE_INTERVAL_MAX_MS = 120 * 1000   # 待机动作之间的最大间隔
IDLE_BUBBLE_CHANCE = 0.35           # 待机时冒独白气泡的概率

# 主动搭话配置
PROACTIVE_MIN_MINUTES = 20          # 主动搭话最小间隔（分钟）
PROACTIVE_MAX_MINUTES = 60          # 主动搭话最大间隔（分钟）

# 宵崎奏（ヨイサキ カナデ）风格台词
# 特点：轻声细语、常带省略号、内向敏感、把作曲/救赎挂在心上、偶尔提到 MEIKO 姐姐
DIALOGUES = [
    "[emotion:curious]……嗯？",
    "[emotion:neutral]……你好。",
    "[emotion:shy]对不起……打扰到你了吗？",
    "[emotion:neutral]……请让我再写一会儿曲子。",
    "[emotion:happy]我……还差一点点就能完成了。",
    "[emotion:sad]如果这首歌，能拯救某个人就好了……",
    "[emotion:happy]……谢谢你，愿意来看我。",
    "[emotion:sad]别担心我……我没事的。",
    "[emotion:neutral]……熬夜对身体不好哦。",
    "[emotion:neutral]……你也，要好好休息。",
    "[emotion:happy]键盘的声音……让人安心呢。",
    "[emotion:happy]……有你在，稍微能安心一点。",
    "[emotion:shy]对不起,我……又走神了。",
    "[emotion:curious]……这段旋律，你觉得怎么样？",
    "[emotion:neutral]……嗯，我在听。",
    "[emotion:neutral]只要还能写下去，就没关系……",
    "[emotion:sad]……绘名她们，一定在等我。",
    "[emotion:shy]对不起,让你担心了……",
    "[emotion:sad]……请不要离开哦。",
    "[emotion:shy]……可以陪我一会儿吗？",
    "[emotion:neutral]只要，还有人需要这首歌……",
]

# 待机时的独白台词（更内向、更像自言自语）
IDLE_DIALOGUES = [
    "[emotion:neutral]……好安静。",
    "[emotion:curious]……嗯，这段旋律再改一下……",
    "[emotion:curious]……你还在吗？",
    "[emotion:neutral]……不知不觉，就这个点了。",
    "[emotion:sleepy]……偶尔发呆一下，也没关系吧。",
    "[emotion:sleepy]……啊，走神了。",
    "[emotion:sad]……绘名，最近还好吗。",
    "[emotion:neutral]……继续，再一点点就好。",
    "[emotion:neutral]……窗外的风，好像变了。",
    "[emotion:neutral]……你不说话，我也不打扰。",
    "[emotion:sleepy]……时间过得，好快啊。",
    "[emotion:neutral]……嗯，先记下来吧。",
]


def resource_path(relative_path: str) -> str:
    """获取资源文件路径（兼容 PyInstaller 单文件打包）"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# --------------------------- 气泡窗口 ---------------------------
class BubbleWindow(QWidget):
    """独立的对话气泡窗口，显示在角色上方，不遮挡角色。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput  # 不接收鼠标事件，避免遮挡
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._text = ""
        self._padding_x = 14
        self._padding_y = 10
        self._tail_h = 10
        self._radius = 12
        self._font = QFont("Microsoft YaHei", 11, QFont.Bold)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, anchor_top_center: QPoint, duration_ms: int = BUBBLE_DURATION_MS):
        self._text = text

        # 计算所需大小（支持自动换行）
        fm = QFontMetrics(self._font)
        max_w = 360  # 气泡最大宽度
        # 用 boundingRect 计算换行后的实际尺寸
        bounding = fm.boundingRect(
            QRect(0, 0, max_w, 10000),
            Qt.TextWordWrap | Qt.AlignCenter,
            text,
        )
        text_w = min(max_w, max(bounding.width(), fm.horizontalAdvance("字字字字")))
        text_h = bounding.height()
        w = text_w + self._padding_x * 2
        h = text_h + self._padding_y * 2 + self._tail_h
        self.resize(w, h)

        # 定位：将气泡底部尾巴中心贴在 anchor_top_center（角色顶部中心）上方 4 px
        x = anchor_top_center.x() - w // 2
        y = anchor_top_center.y() - h - 4

        # 屏幕边界修正
        screen = QApplication.primaryScreen().availableGeometry()
        if x < screen.left():
            x = screen.left() + 2
        if x + w > screen.right():
            x = screen.right() - w - 2
        if y < screen.top():
            y = anchor_top_center.y() + 4  # 若上方不够就放到下方（尾巴仍向下画）

        self.move(x, y)
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        body_rect = QRect(0, 0, w, h - self._tail_h)

        # 气泡主体（圆角矩形 + 底部小三角尾巴）
        path = QPainterPath()
        path.addRoundedRect(body_rect, self._radius, self._radius)

        tail = QPainterPath()
        cx = w // 2
        by = h - self._tail_h
        tail.moveTo(cx - 8, by)
        tail.lineTo(cx + 8, by)
        tail.lineTo(cx, h - 1)
        tail.closeSubpath()

        full = path.united(tail)

        p.setPen(QPen(QColor(80, 80, 100, 220), 1.5))
        p.setBrush(QBrush(QColor(255, 255, 255, 235)))
        p.drawPath(full)

        # 文本（支持自动换行）
        p.setPen(QColor(50, 50, 60))
        p.setFont(self._font)
        text_rect = body_rect.adjusted(
            self._padding_x, self._padding_y,
            -self._padding_x, -self._padding_y,
        )
        p.drawText(
            text_rect,
            Qt.TextWordWrap | Qt.AlignVCenter | Qt.AlignLeft,
            self._text,
        )


# --------------------------- 桌宠主窗口 ---------------------------
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()

        # 先读配置——渲染载体（图片 / Live2D）以及 AstrBot 参数都从这里来
        self._config = load_config()

        # 窗口属性：无边框、透明、置顶、任务栏隐藏
        self._always_on_top = True
        self._apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 初始尺寸
        self._pet_height = DEFAULT_HEIGHT

        # 渲染载体（QLabel+PNG 或 QOpenGLWidget+Live2D）
        self._renderer: PetRenderer = self._make_renderer_from_config()
        self._renderer.natural_size_changed.connect(
            self._on_renderer_natural_size_changed)
        self._renderer.tray_icon_changed.connect(self._refresh_tray_icon)
        self._apply_pet_size()

        # 定位到屏幕右下角
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 40,
                  screen.bottom() - self.height() - 40)

        # 拖动状态
        self._drag_pos = None
        self._is_dragging = False
        self._press_pos = None

        # 滚轮缩放合并（见 wheelEvent）
        self._pending_zoom_height: Optional[int] = None
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setInterval(40)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.timeout.connect(self._apply_pending_zoom)

        # 物理掉落相关
        self._phys_vx = 0.0          # 水平速度 (px/frame)
        self._phys_vy = 0.0          # 垂直速度 (px/frame)
        self._phys_x = 0.0           # 浮点位置 x
        self._phys_y = 0.0           # 浮点位置 y
        self._phys_active = False
        self._physics_enabled = (self._config.get("pet_mode", "image") == "image")
        self._phys_timer = QTimer(self)
        self._phys_timer.setInterval(16)  # ~60fps
        self._phys_timer.timeout.connect(self._physics_step)
        self._drag_velocity_tracker = []  # [(timestamp_ms, QPoint), ...]

        # 气泡
        self._bubble = BubbleWindow()

        # 互动状态
        self._interaction_index = 0
        self._interactions = [
            self._interact_jump,
            self._interact_squash,
            self._interact_shake,
        ]
        self._anim = None  # 保持引用，避免被 GC

        # 基础几何（用于动画中还原）
        self._base_pos = self.pos()
        self._base_size = self.size()

        # AstrBot 聊天：OneBot v11 WS 客户端（主动连远程 AstrBot）
        self._onebot = OneBotClient(self._config, parent=self)
        self._onebot.reply_received.connect(self._on_bot_reply)
        self._onebot.connection_changed.connect(self._on_connection_changed)
        self._onebot.start()

        # 聊天输入窗口
        self._chat_input = ChatInputWindow()
        self._chat_input.message_sent.connect(self._on_user_send)

        # 系统托盘（备用，确保能退出）
        self._init_tray()

        # ---------- 待机动画 ----------
        # 无交互多久后开始播放待机动作；每次动作后再随机间隔触发下一次
        self._idle_enabled = bool(self._config.get("idle_animation", True))
        self._last_interaction_ms = self._elapsed_ms()
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_tick)
        self._idle_actions = [
            self._idle_tilt,        # 微微歪头
            self._idle_breathe,     # 轻微呼吸
            self._idle_doze,        # 打瞌睡
            self._idle_look_around, # 左右张望
        ]
        self._idle_action_index = 0
        if self._idle_enabled:
            self._schedule_idle_check(IDLE_TRIGGER_MS)

        # ---------- 主动搭话 ----------
        # 定时向 AstrBot 发送特殊消息，让 LLM 主动生成一句话
        self._proactive_enabled = bool(self._config.get("proactive_chat", False))
        self._proactive_timer = QTimer(self)
        self._proactive_timer.setSingleShot(True)
        self._proactive_timer.timeout.connect(self._on_proactive_tick)
        if self._proactive_enabled:
            self._schedule_proactive()


    # ---------- 窗口标志 ----------
    def _apply_window_flags(self):
        flags = (Qt.FramelessWindowHint | Qt.Tool
                 | Qt.WindowSystemMenuHint)
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    # ---------- 渲染载体 ----------
    def _make_renderer_from_config(self) -> PetRenderer:
        """按 config 的 pet_mode 创建 renderer。Live2D 失败时回退到图片。"""
        mode = self._config.get("pet_mode", "image")
        img = self._config.get("image_path", "") or resource_path(IMAGE_FILE)
        l2d = self._config.get("live2d_model_path", "")
        try:
            return make_renderer(mode, img, l2d, self)
        except Exception as e:
            print(f"[Renderer] failed to build {mode}: {e}")
            if mode == "image":
                raise
            # Live2D 起不来 → 回落图片模式；延迟弹一个气泡告诉用户
            err = str(e)
            QTimer.singleShot(1500, lambda: self._show_bubble(
                f"……Live2D 加载失败了：\n{err}\n先用图片模式吧。",
                duration_ms=6000))
            fallback = img if img else resource_path(IMAGE_FILE)
            return ImageRenderer(fallback, self)

    def _apply_pet_size(self):
        """按当前 pet_height 让 renderer 重排显示。renderer 自己会 resize 窗口。"""
        size = self._renderer.set_display_height(self._pet_height)
        self._base_size = QSize(size.width(), size.height())

    def _on_renderer_natural_size_changed(self):
        """Live2D 模型加载完拿到真实画布宽高比时触发。以中心为锚点原子重排。"""
        old_geom = self.geometry()
        anchor = old_geom.center()
        new_size = self._renderer.natural_size_for_height(self._pet_height)
        self.setGeometry(anchor.x() - new_size.width() // 2,
                         anchor.y() - new_size.height() // 2,
                         new_size.width(), new_size.height())
        self._renderer.layout_for_size(new_size)
        self._base_size = QSize(new_size.width(), new_size.height())
        self._base_pos = self.pos()

    def _refresh_tray_icon(self):
        """renderer 通知托盘图标变了（或切换角色时）。回落顺序：renderer → 1.png → app.ico"""
        if not hasattr(self, "_tray"):
            return
        icon = self._renderer.tray_icon()
        if icon.isNull():
            icon = self._fallback_tray_icon()
        if not icon.isNull():
            self._tray.setIcon(icon)

    def _fallback_tray_icon(self) -> QIcon:
        """托盘图标兜底：优先 1.png（角色原画），其次 app.ico"""
        for name in (IMAGE_FILE, "app.ico"):
            p = resource_path(name)
            if os.path.exists(p):
                ic = QIcon(p)
                if not ic.isNull():
                    return ic
        return QIcon()

    # ---------- 系统托盘 ----------
    def _init_tray(self):
        icon = self._renderer.tray_icon()
        if icon.isNull():
            icon = self._fallback_tray_icon()
        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        act_show = QAction("显示 / 隐藏", self)
        act_show.triggered.connect(self._toggle_visible)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("Kanade 桌宠")
        self._tray.show()

    def _toggle_visible(self):
        self.setVisible(not self.isVisible())

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 停止物理模拟（如果正在进行）
            self._stop_physics()
            self._note_interaction()
            self._press_pos = event.globalPosition().toPoint()
            self._drag_pos = self._press_pos - self.frameGeometry().topLeft()
            self._is_dragging = False
            self._drag_velocity_tracker.clear()
            self._drag_velocity_tracker.append(
                (self._elapsed_ms(), event.globalPosition().toPoint())
            )
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            gp = event.globalPosition().toPoint()
            # 超过阈值才视为拖动
            if not self._is_dragging:
                if (gp - self._press_pos).manhattanLength() > 4:
                    self._is_dragging = True
            if self._is_dragging:
                self.move(gp - self._drag_pos)
                self._base_pos = self.pos()
                # 记录轨迹用于计算释放速度（只保留最近 5 个点）
                now = self._elapsed_ms()
                self._drag_velocity_tracker.append((now, gp))
                if len(self._drag_velocity_tracker) > 5:
                    self._drag_velocity_tracker.pop(0)
                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._is_dragging:
                # 视为点击 -> 触发互动
                self._trigger_next_interaction()
            else:
                # 拖动释放
                if self._physics_enabled:
                    self._start_physics_from_drag()
                else:
                    self._base_pos = self.pos()
            self._drag_pos = None
            self._is_dragging = False
            event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        step = WHEEL_STEP if delta > 0 else -WHEEL_STEP
        # 滚轮合并：连续滚动只累积目标高度，每 ~40ms 应用一次。
        # 每格都立刻重排的话，GL 帧总比窗口几何晚一拍，连续触发看起来就是抖。
        base = self._pending_zoom_height if self._pending_zoom_height is not None \
            else self._pet_height
        self._pending_zoom_height = max(MIN_HEIGHT, min(MAX_HEIGHT, base + step))
        if not self._zoom_timer.isActive():
            self._zoom_timer.start()
        self._note_interaction()
        event.accept()

    def _apply_pending_zoom(self):
        if self._pending_zoom_height is None:
            return
        target = self._pending_zoom_height
        self._pending_zoom_height = None
        self._resize_pet(target)

    # ---------- 右键菜单 ----------
    def _show_context_menu(self, global_pos):
        menu = QMenu(self)

        size_menu = menu.addMenu("调整大小")
        for label, h in [("小 (160)", 160), ("中 (260)", 260),
                         ("大 (400)", 400), ("超大 (600)", 600)]:
            act = QAction(label, self)
            act.triggered.connect(lambda _=False, hh=h: self._resize_pet(hh))
            size_menu.addAction(act)

        top_act = QAction("始终置顶", self, checkable=True)
        top_act.setChecked(self._always_on_top)
        top_act.triggered.connect(self._toggle_always_on_top)
        menu.addAction(top_act)

        phys_act = QAction("物理掉落", self, checkable=True)
        phys_act.setChecked(self._physics_enabled)
        phys_act.triggered.connect(self._toggle_physics)
        menu.addAction(phys_act)

        switch_act = QAction("切换角色…", self)
        switch_act.triggered.connect(self._open_character_dialog)
        menu.addAction(switch_act)

        menu.addSeparator()

        # AstrBot 聊天
        chat_status = "已连接" if self._onebot.connected else "未连接"
        chat_act = QAction(f"和奏聊天…（AstrBot：{chat_status}）", self)
        chat_act.triggered.connect(self._toggle_chat_input)
        menu.addAction(chat_act)

        info_act = QAction(f"WS 地址：{self._config.get('ws_url','')}", self)
        info_act.setEnabled(False)
        menu.addAction(info_act)

        settings_act = QAction("AstrBot 连接设置…", self)
        settings_act.triggered.connect(self._open_settings)
        menu.addAction(settings_act)

        reconnect_act = QAction("重新连接 AstrBot", self)
        reconnect_act.triggered.connect(self._reconnect_bot)
        menu.addAction(reconnect_act)

        menu.addSeparator()

        idle_act = QAction("待机动画", self, checkable=True)
        idle_act.setChecked(self._idle_enabled)
        idle_act.triggered.connect(self._toggle_idle)
        menu.addAction(idle_act)

        proactive_act = QAction("主动搭话", self, checkable=True)
        proactive_act.setChecked(self._proactive_enabled)
        proactive_act.triggered.connect(self._toggle_proactive)
        menu.addAction(proactive_act)

        menu.addSeparator()

        update_act = QAction(f"检查更新（当前 v{VERSION}）", self)
        update_act.triggered.connect(self._check_for_update)
        menu.addAction(update_act)

        quit_act = QAction("退出程序", self)
        quit_act.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_act)

        menu.exec(global_pos)

    def _toggle_always_on_top(self):
        self._always_on_top = not self._always_on_top
        # 记录位置，重置窗口 flag 后需要重新 show
        pos = self.pos()
        self._apply_window_flags()
        self.show()
        self.move(pos)

    def _toggle_physics(self):
        self._physics_enabled = not self._physics_enabled
        if not self._physics_enabled:
            self._stop_physics()

    def _check_for_update(self):
        """右键菜单"检查更新"入口。"""
        info = check_for_update(VERSION)
        if info is None:
            QMessageBox.information(self, "检查更新", f"当前已是最新版本 v{VERSION}")
            return
        reply = QMessageBox.question(
            self, "发现新版本",
            f"新版本 v{info['version']}（当前 v{VERSION}）\n\n"
            f"更新说明：\n{info['notes'][:300]}\n\n"
            f"是否立即更新？（更新过程需要 1-2 分钟）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        project_dir = os.path.dirname(os.path.abspath(__file__))
        dlg = UpdateDialog(info["zip_url"], project_dir, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.new_exe_path:
            QMessageBox.information(self, "更新完成",
                                   f"更新完成！新版本已打包到：\n{dlg.new_exe_path}\n\n"
                                   f"即将重启...")
            os.startfile(dlg.new_exe_path)
            QApplication.instance().quit()

    def _resize_pet(self, new_height: int):
        new_height = max(MIN_HEIGHT, min(MAX_HEIGHT, int(new_height)))
        if new_height == self._pet_height:
            return
        old_geom = self.geometry()
        anchor = old_geom.center()
        self._pet_height = new_height
        new_size = self._renderer.natural_size_for_height(new_height)
        self.setGeometry(anchor.x() - new_size.width() // 2,
                         anchor.y() - new_size.height() // 2,
                         new_size.width(), new_size.height())
        self._renderer.layout_for_size(new_size)
        self._base_size = QSize(new_size.width(), new_size.height())
        self._base_pos = self.pos()

    # ---------- 互动 ----------
    def _trigger_next_interaction(self):
        """单击释放的顶层反应：委托给渲染层做动画/动作，同时发 poke/兜底气泡。"""
        self._renderer.on_click(self)

        # 戳一戳：优先发 poke 事件给 AstrBot；连不上时 fallback 到本地台词
        if self._onebot.connected:
            ok = self._onebot.send_poke_event()
            if not ok:
                self._show_random_bubble()
            # 否则等 AstrBot 通过 _on_bot_reply 回消息
        else:
            self._show_random_bubble()

    def run_click_animation(self):
        """图片模式的窗口级点击动画（jump/squash/shake 轮播）。由 ImageRenderer 调用。"""
        # 若正在动画，忽略
        if self._anim is not None and self._anim.state() == QPropertyAnimation.Running:
            return
        self._base_pos = self.pos()
        self._base_size = self.size()

        action = self._interactions[self._interaction_index % len(self._interactions)]
        self._interaction_index += 1
        action()

    def _show_random_bubble(self):
        raw = random.choice(DIALOGUES)
        from pet_renderer import parse_emotion_tag
        emotion, text = parse_emotion_tag(raw)
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        self._bubble.show_text(text, anchor)
        if emotion:
            self._renderer.on_message(raw, self)

    def _show_bubble(self, text: str, duration_ms: int = None):
        """在气泡里显示指定文本；根据文字长度自动延长显示时间"""
        anchor = self.mapToGlobal(QPoint(self.width() // 2, 0))
        if duration_ms is None:
            # 每个字符 120ms，最少 2s，最多 12s
            duration_ms = max(2000, min(12000, len(text) * 120))
        self._bubble.show_text(text, anchor, duration_ms=duration_ms)

    # ---------- 聊天相关 ----------
    def _toggle_chat_input(self):
        if self._chat_input.isVisible():
            self._chat_input.hide()
        else:
            self._chat_input.show_near(self.pos(), self.size())

    def _on_user_send(self, text: str):
        """用户在输入框按回车发送消息"""
        if not self._onebot.connected:
            self._show_bubble(
                "……还没连上 AstrBot 呢。请检查 WS 地址：\n"
                f"{self._config.get('ws_url','')}"
            )
            return
        self._onebot.send_user_message(text)
        # 不弹"让我想想"，安静等待回复

    def _on_bot_reply(self, text: str):
        """AstrBot 回复到达，显示在气泡里"""
        if not text:
            return
        from pet_renderer import parse_emotion_tag
        _, clean_text = parse_emotion_tag(text)
        self._show_bubble(clean_text)
        # 让渲染层做个"回话"反应（Live2D 会播对应情绪动作）
        self._renderer.on_message(text, self)

    def _on_connection_changed(self, connected: bool):
        """WS 连接状态变化"""
        if connected:
            self._show_bubble("……嗯，连上了。", duration_ms=1800)
        # 断开时不打扰，静默重连

    def _open_settings(self):
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() == QDialog.Accepted:
            new_cfg = dlg.get_config()
            self._config = new_cfg
            save_config(new_cfg)
            self._onebot.update_config(new_cfg)
            self._show_bubble("……好，我去重新连一下。", duration_ms=2000)

    def _reconnect_bot(self):
        self._onebot.stop()
        QTimer.singleShot(300, self._onebot.start)
        self._show_bubble("……嗯，我再试试。", duration_ms=1500)

    # ---------- 切换角色（图片 / Live2D） ----------
    def _open_character_dialog(self):
        dlg = CharacterDialog(
            current_mode=self._config.get("pet_mode", "image"),
            image_path=self._config.get("image_path", ""),
            live2d_path=self._config.get("live2d_model_path", ""),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        mode, img, l2d = dlg.result_value()
        self._config["pet_mode"] = mode
        self._config["image_path"] = img
        self._config["live2d_model_path"] = l2d
        save_config(self._config)
        self._swap_renderer()

    def _swap_renderer(self):
        """
        原地更换渲染载体：停动画/物理 → 销毁旧 widget → 建新的 → 重排尺寸 → 更新托盘。
        Live2D 的 GL 上下文会随着 widget 析构一起清掉。
        """
        # 停掉一切正在跑的动画
        if self._anim is not None and self._anim.state() == QPropertyAnimation.Running:
            self._anim.stop()
        self._anim = None
        self._stop_physics()

        # 断开旧 renderer 的信号，销毁其 widget
        try:
            self._renderer.natural_size_changed.disconnect(
                self._on_renderer_natural_size_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            self._renderer.tray_icon_changed.disconnect(self._refresh_tray_icon)
        except (TypeError, RuntimeError):
            pass
        old_widget = self._renderer.widget()
        self._renderer.cleanup()
        if old_widget is not None:
            old_widget.hide()
            old_widget.setParent(None)
            old_widget.deleteLater()

        # 建新 renderer；失败时 _make_renderer_from_config 会自动回退到图片
        self._renderer = self._make_renderer_from_config()
        self._renderer.natural_size_changed.connect(
            self._on_renderer_natural_size_changed)
        self._renderer.tray_icon_changed.connect(self._refresh_tray_icon)
        self._physics_enabled = (self._config.get("pet_mode", "image") == "image")
        self._apply_pet_size()
        self._renderer.widget().show()

        # 更新托盘图标（图片模式立即有；Live2D 先回落 app.ico，等截图后由 tray_icon_changed 再更新）
        self._refresh_tray_icon()

        self._show_bubble("……嗯，换了个样子。", duration_ms=1600)

    # ---------- 待机动画 ----------
    def _note_interaction(self):
        """任何用户交互都调用一下：拖动、点击、滚轮、聊天，重置空闲计时。"""
        self._last_interaction_ms = self._elapsed_ms()

    def _schedule_idle_check(self, delay_ms: int):
        """安排下一次待机检查/触发。"""
        if not self._idle_enabled:
            return
        self._idle_timer.start(max(1000, int(delay_ms)))

    def _on_idle_tick(self):
        """待机计时器到点：如果确实空闲够久，就播放一个待机动作。"""
        if not self._idle_enabled:
            return
        idle_for = self._elapsed_ms() - self._last_interaction_ms
        if idle_for < IDLE_TRIGGER_MS:
            # 还没达到空闲阈值，再等剩余时间
            self._schedule_idle_check(IDLE_TRIGGER_MS - idle_for)
            return
        # 若当前正在动画/物理模拟，稍后再试
        anim_running = (self._anim is not None
                        and self._anim.state() == QPropertyAnimation.Running)
        if anim_running or self._phys_active:
            self._schedule_idle_check(5000)
            return

        # 让渲染层挑一个待机动作（图片：窗口动画；Live2D：StartMotion）
        self._renderer.on_idle(self)

        # 有一定概率冒个独白气泡（不依赖具体载体）
        if random.random() < IDLE_BUBBLE_CHANCE:
            raw = random.choice(IDLE_DIALOGUES)
            from pet_renderer import parse_emotion_tag
            emotion, clean = parse_emotion_tag(raw)
            self._show_bubble(clean, duration_ms=2500)
            if emotion:
                self._renderer.on_message(raw, self)

        # 再等一段随机时间做下一次待机
        next_delay = random.randint(IDLE_INTERVAL_MIN_MS, IDLE_INTERVAL_MAX_MS)
        self._schedule_idle_check(next_delay)

    def run_idle_animation(self):
        """图片模式的窗口级 idle 动画。由 ImageRenderer 调用。"""
        action = random.choice(self._idle_actions)
        self._base_pos = self.pos()
        self._base_size = self.size()
        action()

    # ---- 待机动作：微微歪头（水平轻晃一下）----
    def _idle_tilt(self):
        base = self._base_pos
        amp = max(3, self.width() // 60)
        seq = QSequentialAnimationGroup(self)
        offsets = [amp, 0, -amp, 0]
        prev = base
        for off in offsets:
            target = QPoint(base.x() + off, base.y())
            a = QPropertyAnimation(self, b"pos")
            a.setDuration(420)
            a.setStartValue(prev)
            a.setEndValue(target)
            a.setEasingCurve(QEasingCurve.InOutSine)
            seq.addAnimation(a)
            prev = target
        seq.finished.connect(lambda: self.move(base))
        self._anim = seq
        seq.start()

    # ---- 待机动作：轻微呼吸（上下 1~2 px 缓慢起伏）----
    def _idle_breathe(self):
        base = self._base_pos
        amp = max(2, self.height() // 120)
        seq = QSequentialAnimationGroup(self)
        cycle = [(-amp, 900), (0, 900), (-amp, 900), (0, 900)]
        prev = base
        for dy, dur in cycle:
            target = QPoint(base.x(), base.y() + dy)
            a = QPropertyAnimation(self, b"pos")
            a.setDuration(dur)
            a.setStartValue(prev)
            a.setEndValue(target)
            a.setEasingCurve(QEasingCurve.InOutSine)
            seq.addAnimation(a)
            prev = target
        seq.finished.connect(lambda: self.move(base))
        self._anim = seq
        seq.start()

    # ---- 待机动作：打瞌睡（缓慢压扁一点点，再慢慢恢复）----
    def _idle_doze(self):
        base_w = self._base_size.width()
        base_h = self._base_size.height()
        base_pos = self._base_pos

        squash_h = int(base_h * 0.94)
        squash_w = int(base_w * 1.04)
        squash_pos = QPoint(base_pos.x() - (squash_w - base_w) // 2,
                            base_pos.y() + (base_h - squash_h))

        seq = QSequentialAnimationGroup(self)
        for target_size, target_pos, dur in [
            (QSize(squash_w, squash_h), squash_pos, 1400),
            (QSize(base_w, base_h), base_pos, 1400),
        ]:
            grp = QParallelAnimationGroup(self)
            a_size = QPropertyAnimation(self, b"size")
            a_size.setDuration(dur)
            a_size.setEndValue(target_size)
            a_size.setEasingCurve(QEasingCurve.InOutSine)
            a_pos = QPropertyAnimation(self, b"pos")
            a_pos.setDuration(dur)
            a_pos.setEndValue(target_pos)
            a_pos.setEasingCurve(QEasingCurve.InOutSine)
            grp.addAnimation(a_size)
            grp.addAnimation(a_pos)
            seq.addAnimation(grp)

        def _restore():
            self.resize(base_w, base_h)
            self.move(base_pos)

        seq.finished.connect(_restore)
        self._anim = seq
        # 临时放开尺寸限制
        self.setMinimumSize(1, 1)
        self.setMaximumSize(16777215, 16777215)
        seq.start()

    # ---- 待机动作：左右张望（比互动版本更慢更小幅）----
    def _idle_look_around(self):
        base = self._base_pos
        amp = max(4, self.width() // 40)
        seq = QSequentialAnimationGroup(self)
        offsets = [amp, 0, -amp, 0]
        prev = base
        for off in offsets:
            target = QPoint(base.x() + off, base.y())
            a = QPropertyAnimation(self, b"pos")
            a.setDuration(520)
            a.setStartValue(prev)
            a.setEndValue(target)
            a.setEasingCurve(QEasingCurve.InOutSine)
            seq.addAnimation(a)
            prev = target
        seq.finished.connect(lambda: self.move(base))
        self._anim = seq
        seq.start()

    # ---------- 主动搭话 ----------
    def _schedule_proactive(self):
        """安排下一次主动搭话（随机分钟数）"""
        if not self._proactive_enabled:
            return
        minutes = random.randint(PROACTIVE_MIN_MINUTES, PROACTIVE_MAX_MINUTES)
        self._proactive_timer.start(minutes * 60 * 1000)

    def _on_proactive_tick(self):
        """
        主动搭话触发：
        - 若连了 AstrBot：发一条"提示 LLM 主动搭话"的隐藏消息，等回复冒气泡
        - 若没连：直接冒一个本地独白气泡
        """
        if not self._proactive_enabled:
            return

        anim_running = (self._anim is not None
                        and self._anim.state() == QPropertyAnimation.Running)
        if anim_running or self._phys_active:
            # 忙的时候先跳过，1 分钟后再看
            self._proactive_timer.start(60 * 1000)
            return

        if self._onebot.connected:
            # 给 LLM 的"暗号"提示词：告诉它"该主动搭话了"
            # AstrBot 侧的 system prompt 里可以约定：收到这个字符串就主动说一句话
            nickname = self._config.get("nickname", "诶嘿")
            hint = f"[系统提示]距离上次对话已过去一段时间，请你（奏）主动对{nickname}说一句简短温柔的话，不要重复以前说过的内容。"
            self._onebot.send_user_message(hint)
        else:
            # 离线：直接来一句本地独白
            raw = random.choice(IDLE_DIALOGUES)
            from pet_renderer import parse_emotion_tag
            emotion, clean = parse_emotion_tag(raw)
            self._show_bubble(clean, duration_ms=3000)
            if emotion:
                self._renderer.on_message(raw, self)

        # 安排下一次
        self._schedule_proactive()

    def _toggle_idle(self):
        self._idle_enabled = not self._idle_enabled
        self._config["idle_animation"] = self._idle_enabled
        save_config(self._config)
        if self._idle_enabled:
            self._last_interaction_ms = self._elapsed_ms()
            self._schedule_idle_check(IDLE_TRIGGER_MS)
            self._show_bubble("……好，我会自己待着的。", duration_ms=1800)
        else:
            self._idle_timer.stop()
            self._show_bubble("……嗯，我会一直看着你。", duration_ms=1800)

    def _toggle_proactive(self):
        self._proactive_enabled = not self._proactive_enabled
        self._config["proactive_chat"] = self._proactive_enabled
        save_config(self._config)
        if self._proactive_enabled:
            self._schedule_proactive()
            self._show_bubble("……那我，偶尔来找你说话，可以吗？", duration_ms=2400)
        else:
            self._proactive_timer.stop()
            self._show_bubble("……好，不打扰你了。", duration_ms=2000)

    # ---- 动作 1：跳跃 ----
    def _interact_jump(self):
        start = self._base_pos
        peak = QPoint(start.x(), start.y() - int(self.height() * 0.35))

        up = QPropertyAnimation(self, b"pos")
        up.setDuration(240)
        up.setStartValue(start)
        up.setEndValue(peak)
        up.setEasingCurve(QEasingCurve.OutQuad)

        down = QPropertyAnimation(self, b"pos")
        down.setDuration(260)
        down.setStartValue(peak)
        down.setEndValue(start)
        down.setEasingCurve(QEasingCurve.InQuad)

        seq = QSequentialAnimationGroup(self)
        seq.addAnimation(up)
        seq.addAnimation(down)
        seq.finished.connect(lambda: self.move(start))
        self._anim = seq
        seq.start()

    # ---- 动作 2：压扁回弹 ----
    def _interact_squash(self):
        base_w = self._base_size.width()
        base_h = self._base_size.height()
        base_pos = self._base_pos

        squash_h = int(base_h * 0.72)
        squash_w = int(base_w * 1.18)
        squash_pos = QPoint(base_pos.x() - (squash_w - base_w) // 2,
                            base_pos.y() + (base_h - squash_h))

        stretch_h = int(base_h * 1.15)
        stretch_w = int(base_w * 0.92)
        stretch_pos = QPoint(base_pos.x() + (base_w - stretch_w) // 2,
                             base_pos.y() - (stretch_h - base_h))

        seq = QSequentialAnimationGroup(self)

        for target_size, target_pos, dur, ease in [
            (QSize(squash_w, squash_h), squash_pos, 130, QEasingCurve.OutQuad),
            (QSize(stretch_w, stretch_h), stretch_pos, 160, QEasingCurve.OutQuad),
            (QSize(base_w, base_h), base_pos, 180, QEasingCurve.OutBounce),
        ]:
            grp = QParallelAnimationGroup(self)
            a_size = QPropertyAnimation(self, b"size")
            a_size.setDuration(dur)
            a_size.setEndValue(target_size)
            a_size.setEasingCurve(ease)
            a_pos = QPropertyAnimation(self, b"pos")
            a_pos.setDuration(dur)
            a_pos.setEndValue(target_pos)
            a_pos.setEasingCurve(ease)
            grp.addAnimation(a_size)
            grp.addAnimation(a_pos)
            seq.addAnimation(grp)

        def _restore():
            self.resize(base_w, base_h)
            self.move(base_pos)

        seq.finished.connect(_restore)
        self._anim = seq
        # 由于使用 setFixedSize 会限制 size 动画，这里临时放开尺寸限制
        self.setMinimumSize(1, 1)
        self.setMaximumSize(16777215, 16777215)
        seq.start()

    # ---- 动作 3：左右抖动 ----
    def _interact_shake(self):
        base = self._base_pos
        amp = max(8, self.width() // 20)

        seq = QSequentialAnimationGroup(self)
        offsets = [amp, -amp, int(amp * 0.7), int(-amp * 0.7),
                   int(amp * 0.4), int(-amp * 0.4), 0]
        prev = base
        for off in offsets:
            target = QPoint(base.x() + off, base.y())
            a = QPropertyAnimation(self, b"pos")
            a.setDuration(60)
            a.setStartValue(prev)
            a.setEndValue(target)
            a.setEasingCurve(QEasingCurve.InOutSine)
            seq.addAnimation(a)
            prev = target
        seq.finished.connect(lambda: self.move(base))
        self._anim = seq
        seq.start()

    # ---------- 物理掉落 + 弹跳 ----------
    @staticmethod
    def _elapsed_ms():
        """返回一个单调递增的毫秒时间戳"""
        import time
        return int(time.perf_counter() * 1000)

    def _stop_physics(self):
        if self._phys_active:
            self._phys_timer.stop()
            self._phys_active = False

    def _start_physics_from_drag(self):
        """根据拖动轨迹计算释放速度，启动物理模拟"""
        vx, vy = 0.0, 0.0
        tracker = self._drag_velocity_tracker
        if len(tracker) >= 2:
            # 取最早和最晚的采样点算平均速度
            t0, p0 = tracker[0]
            t1, p1 = tracker[-1]
            dt = max(1, t1 - t0)  # ms
            # 转为 px / 16ms (一帧)
            vx = (p1.x() - p0.x()) / dt * 16.0
            vy = (p1.y() - p0.y()) / dt * 16.0

        # 限速，避免飞出太远
        max_v = 45.0
        vx = max(-max_v, min(max_v, vx))
        vy = max(-max_v, min(max_v, vy))

        self._phys_vx = vx
        self._phys_vy = vy
        pos = self.pos()
        self._phys_x = float(pos.x())
        self._phys_y = float(pos.y())
        self._phys_active = True
        self._phys_timer.start()

    def _physics_step(self):
        """每帧物理更新：重力加速、位置移动、地面/墙壁碰撞反弹（缓降）"""
        GRAVITY = 0.35        # 重力加速度 (px/frame^2)，越小掉得越慢
        AIR_DRAG = 0.985      # 空气阻力（每帧 vy 乘以此值），让下降有终端速度
        BOUNCE = 0.45         # 弹性系数（落地反弹保留的速度比例）
        FRICTION_X = 0.94     # 水平摩擦
        MAX_FALL_SPEED = 9.0  # 下落终端速度上限
        STOP_THRESHOLD = 0.6  # 速度低于此且在地面则停止

        screen = QApplication.primaryScreen().availableGeometry()
        pet_w = self.width()
        pet_h = self.height()

        # 地面 = 屏幕可用区域底部
        floor_y = screen.bottom() - pet_h + 1
        ceil_y = screen.top()
        left_x = screen.left()
        right_x = screen.right() - pet_w + 1

        # 更新速度
        self._phys_vy += GRAVITY
        self._phys_vy *= AIR_DRAG  # 空气阻力
        if self._phys_vy > MAX_FALL_SPEED:
            self._phys_vy = MAX_FALL_SPEED  # 终端速度
        self._phys_vx *= FRICTION_X

        # 更新位置
        self._phys_x += self._phys_vx
        self._phys_y += self._phys_vy

        # 碰撞检测 - 地面
        if self._phys_y >= floor_y:
            self._phys_y = floor_y
            self._phys_vy = -abs(self._phys_vy) * BOUNCE

        # 碰撞检测 - 天花板
        if self._phys_y < ceil_y:
            self._phys_y = ceil_y
            self._phys_vy = abs(self._phys_vy) * BOUNCE

        # 碰撞检测 - 左墙
        if self._phys_x < left_x:
            self._phys_x = left_x
            self._phys_vx = abs(self._phys_vx) * BOUNCE

        # 碰撞检测 - 右墙
        if self._phys_x > right_x:
            self._phys_x = right_x
            self._phys_vx = -abs(self._phys_vx) * BOUNCE

        # 移动窗口
        self.move(int(self._phys_x), int(self._phys_y))

        # 判断是否停止：在地面附近且速度很小
        on_floor = abs(self._phys_y - floor_y) < 2
        speed = abs(self._phys_vx) + abs(self._phys_vy)
        if on_floor and speed < STOP_THRESHOLD:
            self._phys_y = floor_y
            self.move(int(self._phys_x), int(self._phys_y))
            self._stop_physics()
            self._base_pos = self.pos()


# -------------------- 配置文件 --------------------
def config_path() -> str:
    """配置文件路径：exe 同目录下 config.json"""
    if hasattr(sys, "_MEIPASS"):
        # 打包后：放在 exe 所在目录
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


DEFAULT_CONFIG = {
    "ws_url": "ws://127.0.0.1:6700",   # AstrBot 反向 WS 端点（改成你 AstrBot 主机的地址）
    "access_token": "",                # 如果 AstrBot 配置了 token 就填
    "self_id": "10001",                # 桌宠模拟的 bot QQ 号（跟 NapCat 那个不能相同）
    "user_id": "20001",                # 桌宠模拟的你的 QQ 号（区分会话记忆）
    "nickname": "诶嘿",                # 奏对你的称呼
    # 载体：图片 or Live2D
    "pet_mode": "image",               # "image" | "live2d"
    "image_path": "",                  # 空 → 用内置 1.png
    "live2d_model_path": "",           # xxx.model3.json 的绝对路径
}


def load_config() -> dict:
    path = config_path()
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[Config] load error: {e}")
    return cfg


def save_config(cfg: dict):
    path = config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Config] save error: {e}")


# -------------------- OneBot v11 WebSocket 客户端 --------------------
class OneBotClient(QObject):
    """
    模拟 OneBot v11 客户端，主动连接远程 AstrBot 的反向 WS 端点。
    跟 NapCat 平级，一起接到 AstrBot 上（只要 self_id 不重复即可）。
    """
    reply_received = Signal(str)
    connection_changed = Signal(bool)  # True=已连接, False=断开

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._ws = None  # type: QWebSocket | None
        self._connected = False
        self._msg_id_counter = 0
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(5000)  # 5s 后重试
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._connect)
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(30000)  # 每 30s 心跳
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._manual_stop = False

    def update_config(self, config: dict):
        """配置更新后重新连接"""
        self._config = config
        self.stop()
        QTimer.singleShot(300, self.start)

    def start(self):
        self._manual_stop = False
        self._connect()

    def stop(self):
        self._manual_stop = True
        self._reconnect_timer.stop()
        self._heartbeat_timer.stop()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._set_connected(False)

    @property
    def connected(self) -> bool:
        return self._connected

    def _set_connected(self, value: bool):
        if self._connected != value:
            self._connected = value
            self.connection_changed.emit(value)

    def _connect(self):
        url = self._config.get("ws_url", "").strip()
        if not url:
            print("[OneBot WS] no url configured")
            return

        # 清理旧连接
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        print(f"[OneBot WS] connecting to {url} ...")
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_connected)
        self._ws.disconnected.connect(self._on_disconnected)
        self._ws.textMessageReceived.connect(self._on_message)
        self._ws.errorOccurred.connect(self._on_error)

        # 构造带 header 的请求（OneBot 标准 header）
        req = QNetworkRequest(QUrl(url))
        self_id = str(self._config.get("self_id", "10001"))
        req.setRawHeader(b"X-Self-ID", self_id.encode())
        req.setRawHeader(b"X-Client-Role", b"Universal")
        req.setRawHeader(b"User-Agent", b"KanadePet-OneBot/1.0")
        token = self._config.get("access_token", "").strip()
        if token:
            req.setRawHeader(b"Authorization", f"Bearer {token}".encode())

        self._ws.open(req)

    def _on_connected(self):
        print("[OneBot WS] connected!")
        self._set_connected(True)
        # 发送 lifecycle connect 事件（OneBot 标准）
        event = {
            "time": int(time.time()),
            "self_id": int(self._config.get("self_id", "10001")),
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }
        self._ws.sendTextMessage(json.dumps(event))
        # 立刻发一次心跳，之后每 30s 一次，让 AstrBot 认为这个 bot 是"在线可用"
        self._send_heartbeat()
        self._heartbeat_timer.start()

    def _on_disconnected(self):
        print("[OneBot WS] disconnected")
        self._heartbeat_timer.stop()
        self._set_connected(False)
        if not self._manual_stop:
            self._reconnect_timer.start()

    def _on_error(self, err):
        print(f"[OneBot WS] error: {err}")

    def _send_heartbeat(self):
        """发送 OneBot v11 心跳元事件，间隔 30s。aiocqhttp 靠心跳维持 bot 在线状态。"""
        if not self._connected or self._ws is None:
            return
        event = {
            "time": int(time.time()),
            "self_id": int(self._config.get("self_id", "10001")),
            "post_type": "meta_event",
            "meta_event_type": "heartbeat",
            "status": {
                "online": True,
                "good": True,
            },
            "interval": 30000,
        }
        self._ws.sendTextMessage(json.dumps(event))

    def send_user_message(self, text: str) -> bool:
        if not self._connected or self._ws is None:
            return False
        self._msg_id_counter += 1
        # message 使用 array 格式（AstrBot / aiocqhttp 要求）
        message_arr = [{"type": "text", "data": {"text": text}}]
        event = {
            "time": int(time.time()),
            "self_id": int(self._config.get("self_id", "10001")),
            "post_type": "message",
            "message_type": "private",
            "sub_type": "friend",
            "message_id": self._msg_id_counter,
            "user_id": int(self._config.get("user_id", "20001")),
            "target_id": int(self._config.get("self_id", "10001")),
            "message": message_arr,
            "raw_message": text,
            "font": 0,
            "sender": {
                "user_id": int(self._config.get("user_id", "20001")),
                "nickname": self._config.get("nickname", "主人"),
                "sex": "unknown",
                "age": 0,
            },
        }
        self._ws.sendTextMessage(json.dumps(event))
        return True

    def send_poke_event(self) -> bool:
        """
        发送 OneBot v11 戳一戳通知事件（好友私聊 poke）。
        AstrBot 那边如果配置了 poke 事件处理（例如 astrbot_plugin_QQBotPoke 之类的插件），
        就会调用 LLM 生成回复，通过 send_private_msg 传回来。
        """
        if not self._connected or self._ws is None:
            return False
        self_id = int(self._config.get("self_id", "10001"))
        user_id = int(self._config.get("user_id", "20001"))
        event = {
            "time": int(time.time()),
            "self_id": self_id,
            "post_type": "notice",
            "notice_type": "notify",
            "sub_type": "poke",
            "user_id": user_id,       # 发起戳的人（主人）
            "target_id": self_id,     # 被戳的人（bot 自己）
            "sender_id": user_id,
        }
        self._ws.sendTextMessage(json.dumps(event))
        return True

    def _on_message(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        action = data.get("action", "")
        params = data.get("params", {})
        echo = data.get("echo")

        reply_text = None

        if action in ("send_private_msg", "send_msg", "send_group_msg"):
            message = params.get("message", "")
            if isinstance(message, list):
                parts = []
                for seg in message:
                    if seg.get("type") == "text":
                        parts.append(seg.get("data", {}).get("text", ""))
                reply_text = "".join(parts)
            elif isinstance(message, str):
                reply_text = message
            resp = {
                "status": "ok",
                "retcode": 0,
                "data": {"message_id": self._msg_id_counter + 1000},
            }
        elif action == "get_login_info":
            resp = {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "user_id": int(self._config.get("self_id", "10001")),
                    "nickname": "奏",
                },
            }
        elif action == "get_version_info":
            resp = {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "app_name": "KanadePet",
                    "app_version": VERSION,
                    "protocol_version": "v11",
                },
            }
        elif action == "get_status":
            resp = {
                "status": "ok",
                "retcode": 0,
                "data": {"online": True, "good": True},
            }
        else:
            resp = {"status": "ok", "retcode": 0, "data": None}

        if echo is not None:
            resp["echo"] = echo
        if self._ws is not None:
            self._ws.sendTextMessage(json.dumps(resp))

        if reply_text:
            self.reply_received.emit(reply_text.strip())


# -------------------- 设置对话框 --------------------
class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AstrBot 连接设置")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(420, 200)

        self._url = QLineEdit(config.get("ws_url", ""))
        self._url.setPlaceholderText("ws://AstrBot主机IP:端口   （例如 ws://192.168.1.10:6700）")
        self._token = QLineEdit(config.get("access_token", ""))
        self._token.setPlaceholderText("留空表示无 token")
        self._self_id = QLineEdit(str(config.get("self_id", "10001")))
        self._self_id.setPlaceholderText("桌宠模拟的 bot QQ 号（不能与 NapCat 相同）")
        self._user_id = QLineEdit(str(config.get("user_id", "20001")))
        self._user_id.setPlaceholderText("桌宠模拟的你自己的 QQ 号（区分记忆会话）")
        self._nickname = QLineEdit(str(config.get("nickname", "诶嘿")))
        self._nickname.setPlaceholderText("奏对你的称呼（例如：诶嘿、老师、主人）")

        form = QFormLayout()
        form.addRow("WS 地址", self._url)
        form.addRow("Access Token", self._token)
        form.addRow("Bot QQ 号", self._self_id)
        form.addRow("用户 QQ 号", self._user_id)
        form.addRow("你的昵称", self._nickname)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_config(self) -> dict:
        return {
            "ws_url": self._url.text().strip(),
            "access_token": self._token.text().strip(),
            "self_id": self._self_id.text().strip() or "10001",
            "user_id": self._user_id.text().strip() or "20001",
            "nickname": self._nickname.text().strip() or "诶嘿",
        }


# -------------------- 聊天输入窗口 --------------------
class ChatInputWindow(QWidget):
    """浮动在桌宠旁边的小输入框"""
    message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(280, 40)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("和奏说点什么……")
        self._input.setGeometry(4, 4, 272, 32)
        self._input.setFont(QFont("Microsoft YaHei", 10))
        self._input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(255,255,255,230);"
            "  border: 1.5px solid rgba(100,100,140,180);"
            "  border-radius: 14px;"
            "  padding: 4px 12px;"
            "}"
        )
        self._input.returnPressed.connect(self._on_enter)

    def _on_enter(self):
        text = self._input.text().strip()
        if text:
            self.message_sent.emit(text)
            self._input.clear()

    def show_near(self, pet_pos: QPoint, pet_size: QSize):
        """显示在桌宠左侧或右侧"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = pet_pos.x() - self.width() - 8
        y = pet_pos.y() + pet_size.height() // 2 - self.height() // 2
        if x < screen.left():
            x = pet_pos.x() + pet_size.width() + 8
        self.move(x, y)
        self.show()
        self._input.setFocus()


# --------------------------- 入口 ---------------------------
def main():
    # 高 DPI 支持
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 让 QOpenGLWidget 拿到带 alpha 通道的默认 surface 格式——Live2D 模式下透明背景所需
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口时不退出，靠菜单退出

    pet = PetWindow()
    pet.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
