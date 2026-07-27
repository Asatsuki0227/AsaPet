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

**AI 对话（可选，两种后端二选一）**
- **AstrBot**：桌宠作为一个 OneBot v11 客户端，反向 WS 连到你的 AstrBot。用 AstrBot 的人格 + 记忆聊天，与 QQ 端 bot（NapCat 等）完全独立。详见 [AstrBot对接说明.md](AstrBot对接说明.md)
- **直连 API**（更轻量）：不用部署 AstrBot，填一个 API key 就能聊。支持任何 OpenAI 兼容接口（DeepSeek / Kimi / 智谱 / SiliconFlow / OpenAI 官方等）。人设用结构化 JSON（`persona.json`）配置，右键"编辑人设…"随时改
- 两者回复都直接冒在桌宠头顶，单击（戳一戳）也能触发回应
- 右键"对话设置…"随时切换后端

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

**动作映射**：程序会读模型的 motion group 名字，按前缀分桶（happy / sad / angry / shy / sleepy / tease / curious / neutral），对话回复时播一个「身体动作 + 表情动作」组合，待机时播小幅动作。如果你的模型不用 Project Sekai 那套 `w-*` / `face_*` 命名，代码会静默降级到"随便播一个"——**换模型后强烈建议看一下 [Live2D动作映射指南.md](Live2D动作映射指南.md)**，里面讲了匹配机制和怎么手动调整 `motion_map.json`。

**情绪标签**：程序支持通过 `[emotion:xxx]` 标签触发对应情绪的动作。标签格式为 `[emotion:happy]`、`[emotion:sad]` 等（也支持 `[表情:xxx]`），可用的情绪有：`happy`、`sad`、`angry`、`shy`、`sleepy`、`tease`、`curious`、`neutral`。

- **AstrBot 回复**：如果你的 LLM system prompt 里约定了在回复中带 `[emotion:xxx]` 标签，桌宠会自动解析并播放对应动作，气泡里只显示去掉标签后的文本。
- **固定台词**：`desktop_pet.py` 顶部的 `DIALOGUES` / `IDLE_DIALOGUES` 列表里的台词也可以带 `[emotion:xxx]` 前缀来指定情绪。如果你想自定义台词，在句子前加上标签即可，例如 `"[emotion:happy]……谢谢你。"`。不加标签也能用，只是会随机选情绪。
- **motion_map.json**：首次加载 Live2D 模型时，程序会在模型目录下自动生成 `motion_map.json`，里面是每个情绪对应哪些动作组的映射。你可以手动编辑这个文件来调整映射关系——比如让 `"happy"` 触发你模型里特定的几个 motion group。

**授权提醒**：Live2D Cubism SDK 商用有独立授权条款，个人非商用免费。详见 [Live2D 官方](https://www.live2d.com/en/download/cubism-sdk/release-license/)。

---

## 启用直连 API 模式（可选，不用装 AstrBot）

如果你只是想让桌宠能聊天，不想折腾 AstrBot 部署，这条路更快：

**1. 拿一个 API key**

任何 OpenAI 兼容的 Chat Completions 接口都行，例如：
- [DeepSeek](https://platform.deepseek.com/)：`https://api.deepseek.com/v1`，模型名 `deepseek-chat`
- [Moonshot / Kimi](https://platform.moonshot.cn/)：`https://api.moonshot.cn/v1`，模型名 `moonshot-v1-8k`
- [智谱 GLM](https://open.bigmodel.cn/)、[SiliconFlow](https://siliconflow.cn/)、OpenAI 官方等同理，换成对应的 Base URL 和模型名即可

**2. 填进设置**

右键 → "对话设置…" → 选"直连 API" → 填 Base URL / API Key → 点"获取"自动拉取该服务商支持的模型列表，下拉选一个 → 确定。如果服务商不支持模型列表接口，也可以直接在模型框里手动输入。

**3.（可选）编辑人设**

右键 → "编辑人设…"，是一个整段粘贴的文本框——直接把你已经写好的完整 system prompt 贴进去就行（比如你在 AstrBot 里用过的那一段），不需要重新拆成字段。保存后立即生效，原样存在项目根目录的 `persona.json` 里，不会被拆分或改写。

**跟 AstrBot 模式的区别**：
- 不需要单独部署任何服务，配置更简单
- 没有长期记忆——对话历史只在程序这次运行期间保留，重启就清空；也没有 AstrBot 的插件生态
- 情绪标签（`[emotion:xxx]`）不是强制的：如果你的 prompt 里约定了它，桌宠会照常解析播放对应 Live2D 动作；不用也完全没问题，只是待机/回复时会随机选一个动作

**API key 安全提醒**：`config.json` 已经在 `.gitignore` 里，不会被提交进仓库，但你自己也别把填了 key 的截图发出去。

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
  "chat_backend": "astrbot",
  "ws_url": "ws://127.0.0.1:6700",
  "access_token": "",
  "self_id": "10001",
  "user_id": "20001",
  "nickname": "主人",
  "api_base_url": "",
  "api_key": "",
  "api_model": "",
  "idle_animation": true,
  "proactive_chat": false,
  "pet_mode": "image",
  "image_path": "",
  "live2d_model_path": ""
}
```

| 字段 | 说明 |
|---|---|
| `chat_backend` | 对话后端："astrbot" 或 "direct_api" |
| `ws_url` | AstrBot 的反向 WS 端点，不用聊天功能就留空 |
| `access_token` | AstrBot 那边配了 token 就填 |
| `self_id` | 桌宠模拟的 bot QQ 号，与 NapCat 不能相同 |
| `user_id` | 桌宠模拟的"你"的 QQ 号，决定 AstrBot 记忆归属 |
| `nickname` | 角色对你的称呼 |
| `api_base_url` | 直连 API 模式的 Base URL，例如 `https://api.deepseek.com/v1` |
| `api_key` | 直连 API 模式的 API key |
| `api_model` | 直连 API 模式的模型名，例如 `deepseek-chat` |
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
├── desktop_pet.py         # 主程序（窗口壳、拖动、菜单、对话后端接入）
├── pet_renderer.py        # 渲染层：ImageRenderer / Live2DRenderer + MotionPicker
├── character_dialog.py    # "切换角色…" 对话框
├── ai_chat.py             # 直连 API 客户端 + 人设 prompt 构建
├── persona_dialog.py      # "编辑人设…" 对话框
├── persona.json           # 直连 API 模式的人设数据（可编辑）
├── AsaPet.spec            # PyInstaller 打包配置
├── requirements.txt       # 依赖清单
├── AstrBot对接说明.md      # 与 AstrBot 集成的详细说明
├── Live2D动作映射指南.md   # 换模型后怎么调整情绪→动作映射
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
A: AstrBot 模式下，在 system prompt 里加一句：
> 如果收到以 `[系统提示]` 开头的消息，请以你的语气主动说一句简短的话，不要复述系统提示的原文。

直连 API 模式已经内置了同样的约定，不用额外配置。

**Q: 直连 API 模式该填哪个 Base URL？**
A: 填服务商文档里 Chat Completions 接口的根地址，不带 `/chat/completions` 后缀。比如 DeepSeek 官方文档给的是 `https://api.deepseek.com/v1/chat/completions`，这里只填 `https://api.deepseek.com/v1`。

**Q: 直连 API 报错"请求失败了"？**
A: 常见原因：Base URL 填错（多/少了斜杠或路径）、API key 无效或欠费、模型名跟服务商不匹配。气泡里会带具体的 HTTP 状态码，可以对着服务商文档排查。

**Q: 点"获取"没拉到模型列表？**
A: 有的服务商不支持标准的 `/models` 列表接口，或者需要先填对 API key 才有权限查询。这种情况下直接在模型框里手动输入模型名即可，不影响正常聊天。

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
