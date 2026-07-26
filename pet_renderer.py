# -*- coding: utf-8 -*-
"""
桌宠渲染层抽象。

两种载体：
- ImageRenderer  —— 单张透明 PNG，用 QLabel 显示，交互靠窗口级 QPropertyAnimation（跳/压/抖）
- Live2DRenderer —— Cubism 3+ Live2D 模型，用 QOpenGLWidget + live2d-py 渲染，交互靠 StartMotion

PetWindow 只维护窗口壳（拖动/托盘/菜单/气泡/AstrBot），把「点击时做什么」「待机时做什么」
「收到消息时做什么」委托给当前 renderer。

Live2D 依赖 live2d-py（`pip install live2d-py`，需 Python ≥ 3.11）。若未安装，Live2DRenderer
构造时抛 RuntimeError，图片模式仍可正常使用。
"""
from __future__ import annotations

import os
import json
import random
from typing import Callable, Optional

from PySide6.QtCore import Qt, QObject, QSize, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

# live2d-py 是可选依赖：图片模式下不需要
try:
    import live2d.v3 as _live2d  # noqa: F401
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    LIVE2D_AVAILABLE = True
except Exception:
    _live2d = None
    QOpenGLWidget = None  # type: ignore
    LIVE2D_AVAILABLE = False


# --------------------------- 抽象基类 ---------------------------
class PetRenderer(QObject):
    """
    渲染载体基类。子类实现具体的显示与交互反应。

    natural_size_changed —— Live2D 场景里，模型加载完后才知道画布宽高比；发这个信号让
    PetWindow 重新按 pet_height 计算窗口尺寸。图片模式 __init__ 里同步就能算好，不发。
    tray_icon_changed —— Live2D 模式启动一小段时间后从渲染画面截图当托盘图标，用这个信号
    通知 PetWindow 去 setIcon。图片模式一次到位不用发。
    """
    natural_size_changed = Signal()
    tray_icon_changed = Signal()

    def widget(self) -> QWidget:
        raise NotImplementedError

    def natural_size_for_height(self, h: int) -> QSize:
        raise NotImplementedError

    def layout_for_size(self, size: QSize) -> None:
        raise NotImplementedError

    def set_display_height(self, h: int) -> QSize:
        raise NotImplementedError

    def tray_icon(self) -> QIcon:
        raise NotImplementedError

    def on_click(self, window) -> None:
        pass

    def on_idle(self, window) -> None:
        pass

    def on_message(self, text: str, window) -> None:
        pass

    def cleanup(self) -> None:
        pass


# --------------------------- 图片模式 ---------------------------
class ImageRenderer(PetRenderer):

    def __init__(self, image_path: str, parent_widget: QWidget):
        super().__init__()
        pix = QPixmap(image_path)
        if pix.isNull():
            raise RuntimeError(f"无法加载图片: {image_path}")
        self._original = pix
        self._scaled: Optional[QPixmap] = None
        self._parent_widget = parent_widget
        self._label = QLabel(parent_widget)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._label.setScaledContents(True)

    def widget(self) -> QWidget:
        return self._label

    def natural_size_for_height(self, h: int) -> QSize:
        ow = self._original.width()
        oh = self._original.height()
        return QSize(max(1, int(ow * h / oh)), h)

    def layout_for_size(self, size: QSize) -> None:
        w, h = size.width(), size.height()
        self._scaled = self._original.scaled(
            w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._label.setPixmap(self._scaled)
        self._label.setGeometry(0, 0, w, h)

    def set_display_height(self, h: int) -> QSize:
        size = self.natural_size_for_height(h)
        self._parent_widget.resize(size)
        self.layout_for_size(size)
        return size

    def tray_icon(self) -> QIcon:
        if self._scaled is not None:
            return QIcon(self._scaled)
        return QIcon(self._original)

    def on_click(self, window) -> None:
        window.run_click_animation()

    def on_idle(self, window) -> None:
        window.run_idle_animation()


# --------------------------- Live2D 模式 ---------------------------
_MOOD_BUCKETS: dict[str, tuple[list[str], list[str]]] = {
    "happy":   (["w-happy-", "w-cute-glad", "w-adult-glad", "w-normal-glad"],
                ["face_smile", "face_sparkling", "face_e"]),
    "sad":     (["w-cool-sad", "w-happy-sad", "w-normal-sad", "w-kanade-sad"],
                ["face_sad", "face_cry"]),
    "angry":   (["w-cool-angry", "w-cute-angry", "w-happy-angry", "w-normal-angry", "w-kanade-angry"],
                ["face_angry"]),
    "shy":     (["w-cute-shy", "w-normal-shy", "w-animal-shy",
                 "w-adult-blushed", "w-cool-blushed", "w-normal-blushed", "w-cute-blushed"],
                ["face_shy", "face_hawawa"]),
    "sleepy":  (["w-cute-sleep"],
                ["face_closeeye", "face_sleepy", "face_tired"]),
    "tease":   (["w-cute-piece", "w-normal-piece", "w-adult-piece", "w-happy-piece",
                 "w-luka-cheek", "w-cute-smug"],
                ["face_smile", "face_e"]),
    "curious": (["w-cute-tilthead", "w-cool-tilthead", "w-normal-tilthead", "w-adult-tilthead",
                 "w-animal-tilthead", "w-kanade-tilthead", "w-happy-tilthead"],
                ["face_baffling", "face_normal"]),
    "neutral": (["w-normal-tilthead", "w-normal-nod", "w-normal-default",
                 "w-cute-tilthead", "w-cool-tilthead", "w-happy-tilthead",
                 "w-animal-fidget", "w-animal-nod", "w-normal-lookleft", "w-normal-lookright"],
                ["face_normal", "face_breath", "face_closeeye"]),
}

_CLICK_MOODS = ["happy", "tease", "curious", "shy"]
_MESSAGE_MOODS = ["happy", "curious", "neutral", "tease"]
_IDLE_MOODS = ["neutral", "sleepy"]


class MotionPicker:

    _COMMON_IDLE = ("Idle", "idle", "")
    _COMMON_TAP = ("TapBody", "tap_body", "Tap", "tap")

    def __init__(self, all_groups: list[str]):
        self._all_groups = list(all_groups)
        self._all_body = [g for g in all_groups if g.startswith("w-")]
        self._all_face = [g for g in all_groups if g.startswith("face_")]
        if not self._all_body and not self._all_face:
            self._all_body = [g for g in all_groups]
        self._buckets: dict[str, tuple[list[str], list[str]]] = {}
        for mood, (body_prefixes, face_prefixes) in _MOOD_BUCKETS.items():
            body_hits = [g for g in self._all_body
                         if any(g.startswith(p) for p in body_prefixes)]
            face_hits = [g for g in self._all_face
                         if any(g.startswith(p) for p in face_prefixes)]
            self._buckets[mood] = (body_hits, face_hits)
        neutral_extra = [g for g in self._all_groups
                         if any(g == n or g.startswith(n) for n in self._COMMON_IDLE if n)]
        if neutral_extra:
            b, f = self._buckets.get("neutral", ([], []))
            self._buckets["neutral"] = (b + neutral_extra, f)
        happy_extra = [g for g in self._all_groups
                       if any(g == n or g.startswith(n) for n in self._COMMON_TAP if n)]
        if happy_extra:
            b, f = self._buckets.get("happy", ([], []))
            self._buckets["happy"] = (b + happy_extra, f)

    def pick(self, mood: str) -> tuple[Optional[str], Optional[str]]:
        bodies, faces = self._buckets.get(mood, ([], []))
        if not bodies:
            bodies = self._all_body
        body = random.choice(bodies) if bodies else None
        face = random.choice(faces) if faces else None
        return body, face


class Live2DGLWidget(QOpenGLWidget if LIVE2D_AVAILABLE else QWidget):
    model_ready = Signal(float)

    def __init__(self, model_json_path: str, parent: Optional[QWidget] = None):
        if not LIVE2D_AVAILABLE:
            raise RuntimeError("live2d-py 未安装，无法使用 Live2D 模式")
        super().__init__(parent)
        self._model_path = model_json_path
        self._model = None
        self._gl_inited = False
        self._picker: Optional[MotionPicker] = None
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)

    def picker(self) -> Optional[MotionPicker]:
        return self._picker

    def start_motion(self, group: str, priority: int) -> None:
        if self._model is None or not group:
            return
        try:
            self._model.StartMotion(group, 0, priority)
        except Exception as e:
            print(f"[Live2D] StartMotion({group}) failed: {e}")

    def initializeGL(self):
        _live2d.glInit()
        self._gl_inited = True
        try:
            self._model = _live2d.LAppModel()
            self._model.LoadModelJson(self._model_path)
            self._model.SetAutoBlinkEnable(True)
            self._model.SetAutoBreathEnable(True)
            try:
                cw, ch = self._model.GetCanvasSize()
                if ch > 0:
                    aspect = float(cw) / float(ch)
                    self.model_ready.emit(aspect)
            except Exception:
                pass
            try:
                groups = list(self._model.GetMotionGroups().keys())
            except Exception:
                try:
                    groups = list(self._model.GetMotionGroups())
                except Exception:
                    groups = []
            self._picker = MotionPicker(groups)
            # 如果模型有 Idle/idle group，起手播一个让模型进入正常姿态
            # （某些模型默认 pose 会叠显所有图层，需要 motion 设参数来隐藏多余的）
            idle_group = None
            for g in groups:
                if g.lower() in ("idle", ""):
                    idle_group = g
                    break
            if idle_group is None:
                for g in groups:
                    if "idle" in g.lower():
                        idle_group = g
                        break
            if idle_group is not None:
                self._model.StartMotion(idle_group, 0, _live2d.MotionPriority.IDLE)
        except Exception as e:
            print(f"[Live2D] load model failed: {e}")
            self._model = None
        self._timer.start()
        if self._model is not None:
            self._model.Resize(self.width(), self.height())

    def resizeGL(self, w: int, h: int):
        if self._model is not None:
            try:
                self._model.Resize(w, h)
            except Exception as e:
                print(f"[Live2D] Resize failed: {e}")

    def paintGL(self):
        _live2d.clearBuffer()
        if self._model is not None:
            try:
                self._model.Update()
                self._model.Draw()
            except Exception as e:
                print(f"[Live2D] draw failed: {e}")

    def cleanup(self):
        self._timer.stop()


class Live2DRenderer(PetRenderer):
    _initialized = False

    def __init__(self, model_json_path: str, parent_widget: QWidget):
        super().__init__()
        if not LIVE2D_AVAILABLE:
            raise RuntimeError("live2d-py 未安装，请先运行：pip install live2d-py")
        if not os.path.exists(model_json_path):
            raise FileNotFoundError(f"找不到 Live2D 模型: {model_json_path}")

        if not Live2DRenderer._initialized:
            _live2d.init()
            Live2DRenderer._initialized = True

        self._model_path = model_json_path
        self._parent_widget = parent_widget
        self._widget = Live2DGLWidget(model_json_path, parent_widget)
        self._widget.model_ready.connect(self._on_model_ready)
        self._tray_icon = QIcon()
        self._aspect = 0.75

    def _on_model_ready(self, aspect: float):
        if aspect > 0 and abs(aspect - self._aspect) > 1e-3:
            self._aspect = aspect
            self.natural_size_changed.emit()

    def widget(self) -> QWidget:
        return self._widget

    def natural_size_for_height(self, h: int) -> QSize:
        return QSize(max(1, int(h * self._aspect)), h)

    def layout_for_size(self, size: QSize) -> None:
        self._widget.setGeometry(0, 0, size.width(), size.height())

    def set_display_height(self, h: int) -> QSize:
        size = self.natural_size_for_height(h)
        self._parent_widget.resize(size)
        self.layout_for_size(size)
        return size

    def tray_icon(self) -> QIcon:
        return self._tray_icon

    def _play_mood(self, mood: str, priority: int):
        picker = self._widget.picker()
        if picker is None:
            return
        body, face = picker.pick(mood)
        if body and (not face or random.random() < 0.7):
            self._widget.start_motion(body, priority)
        elif face:
            self._widget.start_motion(face, priority)

    def on_click(self, window) -> None:
        mood = random.choice(_CLICK_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.NORMAL)

    def on_idle(self, window) -> None:
        mood = random.choice(_IDLE_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.IDLE)

    def on_message(self, text: str, window) -> None:
        mood = random.choice(_MESSAGE_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.NORMAL)

    def cleanup(self):
        self._widget.cleanup()


# --------------------------- 工厂 ---------------------------
def make_renderer(mode: str, image_path: str, live2d_path: str,
                  parent_widget: QWidget) -> PetRenderer:
    if mode == "live2d":
        return Live2DRenderer(live2d_path, parent_widget)
    return ImageRenderer(image_path, parent_widget)
