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
    "happy":   (["glad", "delicious", "guts", "jump", "wink"],
                ["face_smile", "face_sparkling", "face_e"]),
    "sad":     (["sad", "trouble", "sigh"],
                ["face_sad", "face_cry"]),
    "angry":   (["angry", "shakehead"],
                ["face_angry"]),
    "shy":     (["shy", "blushed", "cheek"],
                ["face_shy", "face_hawawa"]),
    "sleepy":  (["sleep", "dizzy", "yurayura"],
                ["face_closeeye", "face_sleepy", "face_tired"]),
    "tease":   (["piece", "smug", "wink", "thumb"],
                ["face_smile", "face_e"]),
    "curious": (["tilthead", "lookaround", "lookaway", "lookleft", "lookright"],
                ["face_baffling", "face_normal"]),
    "neutral": (["nod", "pose", "forward", "relief", "fidget"],
                ["face_normal", "face_breath"]),
}

_CLICK_MOODS = ["happy", "tease", "curious", "shy"]
_MESSAGE_MOODS = ["happy", "curious", "neutral", "tease"]
_IDLE_MOODS = ["neutral", "sleepy"]

# 情绪标签正则：匹配 [emotion:xxx] 或 [表情:xxx]
import re
_EMOTION_TAG_RE = re.compile(r"\[(?:emotion|表情)[：:]([a-zA-Z_]+)\]")


def _generate_motion_map(all_groups: list[str]) -> dict[str, list[str]]:
    """按关键词自动把 group 分到各情绪桶里，返回映射 dict。"""
    import re
    mapping: dict[str, list[str]] = {}
    for mood, (body_keywords, face_prefixes) in _MOOD_BUCKETS.items():
        hits = []
        for g in all_groups:
            if g.startswith("w-"):
                # 取最后一段去掉数字后缀作为关键词
                tail = g.rsplit("-", 1)[-1]
                tail_clean = re.sub(r"\d+$", "", tail).rstrip("B").rstrip("C")
                if tail_clean in body_keywords:
                    hits.append(g)
            elif g.startswith("face_"):
                if any(g.startswith(p) for p in face_prefixes):
                    hits.append(g)
        mapping[mood] = hits
    mapping.setdefault("click", mapping.get("happy", [])[:8] + mapping.get("tease", [])[:5])
    mapping.setdefault("idle", mapping.get("neutral", [])[:8] + mapping.get("sleepy", [])[:5])
    return mapping


def _load_or_create_motion_map(model_json_path: str, all_groups: list[str]) -> dict[str, list[str]]:
    """
    在模型同目录下找 motion_map.json。
    存在就读取（用户可能手动调过），不存在就自动生成一份。
    """
    model_dir = os.path.dirname(model_json_path)
    map_path = os.path.join(model_dir, "motion_map.json")
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 自动生成
    mapping = _generate_motion_map(all_groups)
    try:
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return mapping


# 眨眼参数：固定表情时不锁这两个，交给 SetAutoBlinkEnable 继续驱动
_EYE_OPEN_PARAMS = {"ParamEyeLOpen", "ParamEyeROpen"}


def _load_face_params(model_json_path: str, group: str) -> dict[str, float]:
    """
    把 face_xxx motion 的参数曲线读成 {param_id: value}。

    face_* 的 motion3.json 里每条 Parameter 曲线首尾值恒定（Segments = [t0, v0, type, t1, v1]），
    所以取 v0 就等价于「这个表情下该参数应该是多少」。解析失败返回空 dict，静默降级。
    """
    try:
        model_dir = os.path.dirname(model_json_path)
        with open(model_json_path, "r", encoding="utf-8") as f:
            model_json = json.load(f)
        entries = model_json.get("FileReferences", {}).get("Motions", {}).get(group, [])
        if not entries:
            return {}
        rel = entries[0].get("File", "")
        if not rel:
            return {}
        motion_path = os.path.join(model_dir, rel)
        with open(motion_path, "r", encoding="utf-8") as f:
            motion_json = json.load(f)
        params: dict[str, float] = {}
        for curve in motion_json.get("Curves", []):
            if curve.get("Target") != "Parameter":
                continue
            pid = curve.get("Id")
            if pid in _EYE_OPEN_PARAMS:
                continue  # 眨眼交给 SetAutoBlinkEnable，不锁死
            segments = curve.get("Segments", [])
            if pid and len(segments) >= 2:
                params[pid] = float(segments[1])
        return params
    except Exception as e:
        print(f"[Live2D] load face params({group}) failed: {e}")
        return {}


def parse_emotion_tag(text: str) -> tuple[Optional[str], str]:
    """
    从文本中提取 [emotion:xxx] 标签。
    返回 (emotion_or_None, 去掉标签后的文本)。
    """
    m = _EMOTION_TAG_RE.search(text)
    if m:
        emotion = m.group(1).lower()
        clean_text = text[:m.start()] + text[m.end():]
        return emotion, clean_text.strip()
    return None, text


class MotionPicker:

    _COMMON_IDLE = ("Idle", "idle", "")
    _COMMON_TAP = ("TapBody", "tap_body", "Tap", "tap")

    def __init__(self, all_groups: list[str], motion_map: Optional[dict[str, list[str]]] = None):
        self._all_groups = list(all_groups)
        self._all_body = [g for g in all_groups if g.startswith("w-")]
        self._all_face = [g for g in all_groups if g.startswith("face_")]
        if not self._all_body and not self._all_face:
            self._all_body = [g for g in all_groups]

        if motion_map:
            # 从用户自定义映射文件初始化，只保留模型里实际存在的 group
            group_set = set(all_groups)
            self._map: dict[str, list[str]] = {}
            for mood, groups in motion_map.items():
                valid = [g for g in groups if g in group_set]
                self._map[mood] = valid
        else:
            # 按关键词分桶
            import re as _re
            self._map = {}
            for mood, (body_keywords, face_prefixes) in _MOOD_BUCKETS.items():
                body_hits = []
                for g in self._all_body:
                    tail = g.rsplit("-", 1)[-1]
                    tail_clean = _re.sub(r"\d+$", "", tail).rstrip("B").rstrip("C")
                    if tail_clean in body_keywords:
                        body_hits.append(g)
                face_hits = [g for g in self._all_face
                             if any(g.startswith(p) for p in face_prefixes)]
                self._map[mood] = body_hits + face_hits
            # 官方命名兜底
            neutral_extra = [g for g in self._all_groups
                             if any(g == n or g.startswith(n) for n in self._COMMON_IDLE if n)]
            if neutral_extra:
                self._map["neutral"] = self._map.get("neutral", []) + neutral_extra
            happy_extra = [g for g in self._all_groups
                           if any(g == n or g.startswith(n) for n in self._COMMON_TAP if n)]
            if happy_extra:
                self._map["happy"] = self._map.get("happy", []) + happy_extra

    def pick(self, mood: str) -> Optional[str]:
        """
        从指定情绪桶里随机挑一个身体动作返回。

        表情由「固定表情」机制单独负责（见 Live2DGLWidget.set_fixed_face），所以这里
        只挑身体动作，不会回落到 face_* —— 否则播表情就没身体动作了。
        """
        groups = [g for g in self._map.get(mood, []) if g.startswith("w-")]
        if not groups:
            groups = self._all_body
        if not groups:
            groups = self._all_groups
        return random.choice(groups) if groups else None

    def available_moods(self) -> list[str]:
        """返回有至少一个动作的情绪列表。"""
        return [m for m, g in self._map.items() if g]

    def pick_face(self, mood: str) -> Optional[str]:
        """从指定情绪桶里随机挑一个表情（face_*）返回，没有就 None。"""
        faces = [g for g in self._map.get(mood, []) if g.startswith("face_")]
        return random.choice(faces) if faces else None


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
        self._all_groups: list[str] = []
        self._fixed_face_name: Optional[str] = None
        self._fixed_face_params: dict[str, float] = {}
        self._pending_face: Optional[str] = None
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)

    def picker(self) -> Optional[MotionPicker]:
        return self._picker

    def set_fixed_face(self, group: Optional[str]) -> None:
        """
        固定一个表情。传 None 取消固定，回到由身体动作自带表情驱动。

        实现方式不是 StartMotion（那样会顶掉身体动作），而是把表情解析成一组参数值，
        在每帧 Update() 之后覆盖写入。眨眼参数（ParamEyeLOpen/ROpen）被排除在外，
        始终交给 SetAutoBlinkEnable 驱动，所以固定表情期间眼睛照常眨。
        """
        if self._model is None:
            # GL 还没起来，记下来等 initializeGL 里补上
            self._pending_face = group
            return

        if not group:
            # 不调 ResetParameters —— 那会把身体/服装图层参数一起打回默认值，
            # 露出模型默认姿态里叠在一起的多余图层（之前的"四只手"就是这个原因）。
            # 清空覆盖表就够了：下一帧 Update() 会让当前动作重新接管所有参数。
            self._fixed_face_name = None
            self._fixed_face_params = {}
            return

        params = _load_face_params(self._model_path, group)
        if not params:
            return
        self._fixed_face_name = group
        self._fixed_face_params = params

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
            self._all_groups = groups
            motion_map = _load_or_create_motion_map(self._model_path, groups)
            self._picker = MotionPicker(groups, motion_map)
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
            # 默认锁一个中性表情；点击/对话会临时切换，待机时保持不变
            default_face = self._picker.pick_face("neutral")
            if default_face:
                self.set_fixed_face(default_face)
        except Exception as e:
            print(f"[Live2D] load model failed: {e}")
            self._model = None
        self._timer.start()
        if self._model is not None:
            self._model.Resize(self.width(), self.height())
            # GL 就绪前设过的固定表情，这时候才能真正应用
            if self._pending_face:
                pending, self._pending_face = self._pending_face, None
                self.set_fixed_face(pending)

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
                # Update() 刚把当前 motion 的曲线写进参数，这里覆盖掉脸部那几十个，
                # 于是身体照着动作走、表情保持用户选的那个。顺序不能反。
                if self._fixed_face_params:
                    for pid, val in self._fixed_face_params.items():
                        self._model.SetParameterValue(pid, val)
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

    def _play_mood(self, mood: str, priority: int, switch_face: bool = False):
        picker = self._widget.picker()
        if picker is None:
            return
        group = picker.pick(mood)
        if group:
            self._widget.start_motion(group, priority)
        if switch_face:
            face = picker.pick_face(mood)
            if face:
                self._widget.set_fixed_face(face)

    def on_click(self, window) -> None:
        # 戳一戳：身体动作 + 表情都跟着换，互动感更强
        mood = random.choice(_CLICK_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.NORMAL, switch_face=True)

    def on_idle(self, window) -> None:
        # 待机：只动身体，脸保持不变，不然没人看的时候表情也在乱切很奇怪
        mood = random.choice(_IDLE_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.IDLE)

    def on_message(self, text: str, window) -> None:
        emotion, _ = parse_emotion_tag(text)
        mood = emotion if emotion else random.choice(_MESSAGE_MOODS)
        self._play_mood(mood, _live2d.MotionPriority.NORMAL, switch_face=True)

    def cleanup(self):
        self._widget.cleanup()


# --------------------------- 工厂 ---------------------------
def make_renderer(mode: str, image_path: str, live2d_path: str,
                  parent_widget: QWidget) -> PetRenderer:
    if mode == "live2d":
        return Live2DRenderer(live2d_path, parent_widget)
    return ImageRenderer(image_path, parent_widget)
