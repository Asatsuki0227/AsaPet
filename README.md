# AsaPet · 桌面宠物

一个 Windows 桌面宠物。窗口透明、无边框、始终置顶，可拖动、可弹跳、有互动、有气泡，也可以选择挂到 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 上跟 LLM 聊天。

角色示例是《世界计划 缤纷舞台》里的宵崎奏，但**代码本身与角色无关**，你可以把 `1.png` 换成任何 PNG 图片，桌宠就变成你想要的样子。

---

## 功能

**基础互动**
- 无边框、透明背景、始终置顶（可开关）
- 左键拖动摆放，甩出去会有真实感的重力/弹跳
- 单击轮流触发：跳跃 / 压扁回弹 / 左右抖动
- 每次互动随机冒气泡（不遮挡角色）
- 鼠标滚轮缩放
- 右键菜单：调整大小、置顶开关、待机/主动搭话开关、退出

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
git clone https://github.com/<your-name>/AsaPet.git
cd AsaPet

# 建议用虚拟环境
python -m venv .venv
.venv\Scripts\activate

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

## 素材说明（重要）

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
  "proactive_chat": false
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
├── desktop_pet.py         # 主程序
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

- Python 3.10+（开发用的是 3.14，向下兼容到 3.10 应该没问题）
- [PySide6](https://pypi.org/project/PySide6/)（Qt for Python），用到了 `QtWidgets` / `QtWebSockets`
- 打包用 [PyInstaller](https://pyinstaller.org/)

---

## License

[MIT](LICENSE) © 2026 lieber

代码可自由使用/修改/再分发。**角色美术素材不在本许可证范围内**，请自行确认你使用的素材的版权与授权。
