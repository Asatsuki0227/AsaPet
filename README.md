# AsaPet · 桌面宠物

一个 Windows 桌面宠物。窗口透明、无边框、始终置顶，可拖动、可弹跳、有互动、有气泡，也可以选择挂到 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 上跟 LLM 聊天。

**载体可选：透明 PNG 图片，或 Live2D 模型**（Cubism 3+）。前者轻量，后者能真正动起来。

角色示例是《世界计划 缤纷舞台》里的宵崎奏，但**代码本身与角色无关**，你可以把 `1.png` 换成任何 PNG 图片，或用菜单里的"切换角色…"挂载你自备的 Live2D 模型。

---

## 功能

**基础互动**
- 无边框、透明背景、始终置顶（可开关）
- 左键拖动摆放，甩出去会有真实感的重力/弹跳
- 单击轮流触发：跳跃 / 压扁回弹 / 左右抖动（图片模式）；随机播放身体 + 表情动作组合（Live2D 模式）
- 每次互动随机冒气泡（不遮挡角色）
- 鼠标滚轮缩放
- 右键菜单：调整大小、置顶开关、**切换角色（图片 / Live2D）**、待机/主动搭话开关、退出

**"活着"的感觉**
- **待机动画**：3 分钟没人理它，会自己微微歪头 / 呼吸 / 打瞌睡 / 张望，偶尔冒句独白
- **主动搭话**（可选）：每 20~60 分钟主动来一句
- 系统托盘图标，可最小化显示

**AstrBot 集成（可选）**
- 桌宠可以作为一个 OneBot v11 客户端，反向 WS 连到你的 AstrBot
- 用 AstrBot 的人格 + 记忆聊天，回复直接冒在桌宠头顶
- 与 QQ 端 bot（NapCat 等）完全独立，不互相干扰
- 单击（戳一戳）也能触发 LLM 回应
- 详见 [AstrBot对接说明.md](AstrBot对接说明.md)

---

## 快速开始

### 方式 A：直接跑源码

```bash
git clone https://github.com/Asatsuki0227/AsaPet.git
cd AsaPet

pip install -r requirements.txt

# 把你喜欢的 PNG 图（建议已抠除背景）放到项目根目录，命名为 1.png
# 然后：
python desktop_pet.py
```

### 方式 B：自己打包 EXE

```bash
pip install pyinstaller
pyinstaller AsaPet.spec --noconfirm
# 打包完 dist\AsaPet.exe 直接双击运行
```

`AsaPet.spec` 里默认会把 `1.png` 打包进 EXE，所以打包前记得把你要用的角色图放到项目根目录。

---

## 启用 Live2D 模式（可选）

想让桌宠用真正的 Live2D 模型动起来（眨眼、呼吸、身体+表情分层动作），按下面步骤：

**1. 装依赖**

```bash
pip install live2d-py
```

- 要求 **Python ≥ 3.11**（本项目默认已满足）
- Windows x64 有预编译 wheel，会顺带把 Cubism Core DLL 装好
- 只装图片模式不需要这个包

**2. 准备一个 Cubism 3+ 模型**

需要一份完整的 Live2D 模型目录，至少包含：
- `xxx.model3.json`（入口）
- `xxx.moc3`
- 贴图目录（通常 `xxx.2048/texture_00.png`）
- 建议：`motions/` 里放 motion 文件；`physics3.json` 有更自然的物理

**仓库不含任何模型资产**——请自备。不要把你不拥有版权的官方角色模型放进你的公开仓库。

**3. 切换**

启动程序 → 右键 → "切换角色…" → 选 "Live2D 模式" → 浏览到你的 `xxx.model3.json` → 确定。选择会写进 `config.json`，下次启动直接生效。

**动作映射**：程序会读模型的 motion group 名字，按前缀分桶（happy / sad / angry / shy / sleepy / tease / curious / neutral），单击时随机播一个「身体动作 + 表情动作」组合，待机时播小幅动作。如果你的模型不用 Project Sekai 那套 `w-*` / `face_*` 命名，代码会静默降级到"随便播一个"——想要更精细的映射可以改 `pet_renderer.py` 里的 `_MOOD_BUCKETS`。

**情绪标签**：程序支持通过 `[emotion:xxx]` 标签触发对应情绪的动作。标签格式为 `[emotion:happy]`、`[emotion:sad]` 等（也支持 `[表情:xxx]`），可用的情绪有：`happy`、`sad`、`angry`、`shy`、`sleepy`、`tease`、`curious`、`neutral`。

- **AstrBot 回复**：如果你的 LLM system prompt 里约定了在回复中带 `[emotion:xxx]` 标签，桌宠会自动解析并播放对应动作，气泡里只显示去掉标签后的文本。
- **固定台词**：`desktop_pet.py` 顶部的 `DIALOGUES` / `IDLE_DIALOGUES` 列表里的台词也可以带 `[emotion:xxx]` 前缀来指定情绪。如果你想自定义台词，在句子前加上标签即可，例如 `"[emotion:happy]……谢谢你。"`。不加标签也能用，只是会随机选情绪。
- **motion_map.json**：首次加载 Live2D 模型时，程序会在模型目录下自动生成 `motion_map.json`，里面是每个情绪对应哪些动作组的映射。你可以手动编辑这个文件来调整映射关系——比如让 `"happy"` 触发你模型里特定的几个 motion group。

**授权提醒**：Live2D Cubism SDK 商用有独立授权条款，个人非商用免费。详见 [Live2D 官方](https://www.live2d.com/en/download/cubism-sdk/release-license/)。

---

**仓库里不附带任何角色图片**。你需要自行准备一张 PNG 图（建议已抠除背景），放到项目根目录并命名为 `1.png`。

- 如果你的图片文件名不是 `1.png`，改 `desktop_pet.py` 顶部的 `IMAGE_FILE` 变量即可
- 抠图可以用 [remove.bg](https://www.remove.bg/) 或本地工具
- **请勿在你的仓库里放你不拥有版权的官方角色美术素材**。用自绘图、AI 生图、二创图，或明确允许再分发的素材

---

## 配置文件

首次启动会在 EXE / `desktop_pet.py` 同目录生成 `config.json`，你也可以从右键菜单里改。字段：

```json
{
  "ws_url": "ws://127.0.0.1:6700",
  "access_token": "",
  "self_id": "10001",
  "user_id": "20001",
  "nickname": "主人",
  "idle_animation": true,
  "proactive_chat": false,
  "pet_mode": "image",
  "image_path": "",
  "live2d_model_path": ""
}
```

| 字段 | 说明 |
|---|---|
| `ws_url` | AstrBot 的反向 WS 端点，不用聊天功能就留空 |
| `access_token` | AstrBot 那边配了 token 就填 |
| `self_id` | 桌宠模拟的 bot QQ 号，与 NapCat 不能相同 |
| `user_id` | 桌宠模拟的"你"的 QQ 号，决定 AstrBot 记忆归属 |
| `nickname` | 角色对你的称呼 |
| `idle_animation` | 是否开启待机动画（3 分钟空闲后触发） |
| `proactive_chat` | 是否开启主动搭话（每 20~60 分钟一次） |
| `pet_mode` | 载体："image" 或 "live2d" |
| `image_path` | 图片模式的图片路径，留空则用内置 1.png |
| `live2d_model_path` | Live2D 模式的 .model3.json 绝对路径 |

---

## 常用操作

| 操作 | 结果 |
|---|---|
| 左键单击 | 触发一次互动（跳/压扁/抖动） |
| 左键按住拖动 | 移动桌宠；快速甩出会有惯性弹跳 |
| 滚轮上/下 | 放大/缩小 |
| 右键 | 打开菜单 |
| 3 分钟不动 | 桌宠开始自己待机 |

---

## 目录结构

```
AsaPet/
├── desktop_pet.py         # 主程序（窗口壳、拖动、菜单、AstrBot 集成）
├── pet_renderer.py        # 渲染层：ImageRenderer / Live2DRenderer + MotionPicker
├── character_dialog.py    # "切换角色…" 对话框
├── AsaPet.spec            # PyInstaller 打包配置
├── requirements.txt       # 依赖清单
├── AstrBot对接说明.md      # 与 AstrBot 集成的详细说明
├── app.ico                # 程序图标
├── 1.png                  # 角色图片（用户自备，不入仓库）
├── LICENSE                # MIT
└── README.md
```

---

## 常见问题

**Q: 双击 EXE 没反应？**
A: 大概率是被杀软误杀。PyInstaller 打的 EXE 常被误报，加白名单即可，或用源码方式运行。

**Q: 图片有黑框/白边？**
A: 原图没抠干净背景。用 remove.bg 或类似工具处理后再放进来。

**Q: 想改互动动作、台词或独白？**
A: 直接改 `desktop_pet.py` 顶部的 `DIALOGUES` / `IDLE_DIALOGUES` 列表；动作在 `_interact_jump / _interact_squash / _interact_shake` 三个方法里。

**Q: 待机 3 分钟太长了 / 主动搭话太频繁？**
A: 改 `desktop_pet.py` 顶部这几个常量：
```python
IDLE_TRIGGER_MS = 3 * 60 * 1000        # 空闲多久后开始待机
PROACTIVE_MIN_MINUTES = 20             # 主动搭话最小间隔（分钟）
PROACTIVE_MAX_MINUTES = 60             # 主动搭话最大间隔（分钟）
```

**Q: 怎么让 LLM 更好地回应"主动搭话"？**
A: 在 AstrBot 的 system prompt 里加一句：
> 如果收到以 `[系统提示]` 开头的消息，请以你的语气主动说一句简短的话，不要复述系统提示的原文。

---

## 技术栈

- Python 3.11+（Live2D 模式需要；纯图片模式 3.10 也能跑）
- [PySide6](https://pypi.org/project/PySide6/)（Qt for Python），用到了 `QtWidgets` / `QtWebSockets` / `QtOpenGLWidgets`
- [live2d-py](https://github.com/Arkueid/live2d-py)（可选）—— Cubism SDK 5 的 Python 绑定
- 打包用 [PyInstaller](https://pyinstaller.org/)

---

## License

[MIT](LICENSE) © 2026 lieber

代码可自由使用/修改/再分发。**角色美术素材不在本许可证范围内**，请自行确认你使用的素材的版权与授权。
