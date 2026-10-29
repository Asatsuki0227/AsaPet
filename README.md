# AsaPet · 智能 Live2D 桌面宠物

一款基于 **PySide6** 与 **live2d-py** 开发的高自由度、拟真交互的 Windows 桌面宠物。

支持 **Live2D 动态模型与 PNG 透明立绘双模式**，具备 **物理重力碰撞与抛掷**、**高分屏 DPI 自适应鼠标透明穿透**、**直连大语言模型（LLM）对话**、**原生本地长短期记忆系统** 以及 **AI 自主动作挑选**。

---

## ✨ 核心特性

- 🎨 **双形态渲染（Live2D / PNG 图片）**：随时无缝切换。Live2D 拥有动作、表情、口型与点击反馈；图片模式轻巧极简。
- 🖱️ **完美鼠标透明穿透（DPI 自适应）**：彻底告别误触！结合 Win32 `WS_EX_TRANSPARENT` 与高精度 Alpha 像素采样，只有点中角色实体才响应交互，透明区域完全穿透到后台正在使用的软件；在 125%、150%、200% 等任意高分屏 DPI 缩放下均精准无误。
- ⚡ **真实物理引擎**：开启物理掉落后，支持抓取、抛飞、惯性拖拽、重力下落与地面弹跳、阻尼减速。
- 🧠 **原生本地记忆系统（无需任何外部服务）**：
  - **短期上下文持久化**：自动在本地保存最近对话上下文（`chat_history.json`），即使重启程序也能延续刚才的话题；
  - **长期事实记忆沉淀**：在日常交谈中，后台无感异步提炼你的喜好、习惯、日常安排与近况（`memory.json`），并自然融入人设，像多年相伴的伙伴一样自然关心你；
  - **可视化「记忆管理」窗口**：右键随时查看、手动添加、修改、删除记忆，或一键清空上下文开启全新话题。
- 🎬 **AI 自主挑选动作**：可调用主对话模型或独立的本地小模型（如本地 Ollama 跑的 deepseek-r1），根据每句回复的语气与情绪自动挑选最匹配的 Live2D 动作，无需在 prompt 里硬塞格式。
- 🎭 **完全自由的人设自定义**：右键「编辑人设…」整段粘贴角色 system prompt（支持自由约定称呼、性格、世界观），原样生效，不强加额外格式限制。
- ⏰ **贴心桌面陪伴**：支持定时主动搭话、待机动作随机轮转、戳一戳互动、Windows 开机自启。

---

## 🚀 快速开始

### 方式 A：直接下载 Release 开箱即用（推荐）
1. 前往项目的 [GitHub Releases](https://github.com/Asatsuki0227/AsaPet/releases) 页面；
2. 下载最新的 `AsaPet-Windows-x64.zip`，解压到任意英文路径；
3. 双击 `AsaPet.exe` 即可启动运行。

### 方式 B：从源码运行
#### 环境准备
- 操作系统：Windows 10 / 11 64 位
- Python 版本：Python 3.10 ~ 3.14 64 位

```bash
# 1. 克隆仓库
git clone https://github.com/Asatsuki0227/AsaPet.git
cd AsaPet

# 2. 安装依赖
pip install PySide6 live2d-py

# 3. 运行桌宠
python desktop_pet.py
```

---

## ⚙️ 配置 AI 对话

AsaPet 原生支持直连任何 **OpenAI 兼容接口**（如 DeepSeek、Kimi、智谱、SiliconFlow、OpenAI 官方、Gemini、本地 Ollama / vLLM 等），无需在后台运行任何复杂中间服务。

1. **配置接口**：
   - 右键桌宠，点击 **「模型：未配置」**（已配置时显示当前模型名）；
   - 填写 **Base URL**（例如 `https://api.deepseek.com/v1`）；
   - 填写 **API Key**；
   - 点击 **「获取」** 按钮，从服务商接口自动拉取模型列表，选中你喜欢的模型（例如 `deepseek-chat`）；
   - 点击 **确定** 保存。
2. **编辑角色人设**：
   - 右键桌宠 → **「编辑人设…」**；
   - 整段粘贴你写好的 System Prompt（如角色背景、语气口吻、称呼习惯等）；
   - 保存后即时生效。
3. **查看与管理记忆**：
   - 右键桌宠 → **「记忆管理…」**；
   - 可在 **长期事实记忆** 标签页查看桌宠在聊天中记住的关于你的事情，支持手动增删改；
   - 可在 **对话上下文历史** 标签页按时间浏览近期聊天记录，支持一键清空上下文。

---

## 🎮 常用操作与鼠标手势

| 操作 | 对应效果 |
| :--- | :--- |
| **单击身体** | 播放随机动作 / 触发角色戳一戳回复 |
| **双击身体** | 呼出桌面浮动聊天输入框 |
| **鼠标左键按住拖动** | 抓起移动位置；拖拽中松开可触发物理抛飞 |
| **鼠标滚轮** | 实时放大 / 缩小角色（高度 120px ~ 800px） |
| **鼠标右键** | 打开功能菜单（模型配置、人设、记忆管理、动作库、开机自启等） |

---

## 📂 角色素材导入指南

### 1. 切换自己的 Live2D 模型
- 支持 Cubism 3 / 4 / 5（`.model3.json`）格式的 Live2D 模型；
- 右键菜单 → **「切换角色…」** → 选择「Live2D 模式」→ 点击「浏览…」选择你的 `.model3.json` 文件即可；
- 模型目录下通常包含 `.moc3`、贴图文件夹、物理配置文件以及 `.motion3.json` 动作文件。

### 2. 使用静态/透明 PNG 图片
- 支持任意透明背景的 PNG 格式立绘；
- 右键菜单 → **「切换角色…」** → 选择「静态图片」→ 选择你的 PNG 图片即可。

---

## 🛠️ 打包为单个独立 EXE

如果你修改了源码并希望打包成单文件 EXE 分享给他人：

```bash
# 使用仓库内置的 spec 文件打包
python -m PyInstaller AsaPet.spec
```

打包完成后，产物位于 `dist\AsaPet.exe`，直接双击即可运行。

---

## 📁 核心目录结构

```text
AsaPet/
├── desktop_pet.py           # 桌宠主程序与窗口逻辑（物理引擎、穿透、菜单等）
├── ai_chat.py               # AI 客户端（OpenAI 兼容通信、长短期记忆流、动作挑选）
├── pet_renderer.py          # 渲染抽象层（Live2D 渲染器与图片渲染器）
├── memory_dialog.py         # 可视化记忆与历史管理对话框
├── persona_dialog.py        # 人设 System Prompt 编辑对话框
├── character_dialog.py      # 模型与角色形态切换对话框
├── motion_editor_dialog.py  # Live2D 动作库测试与选择窗口
├── updater.py               # 检查更新组件
├── AsaPet.spec              # PyInstaller 打包规格文件
├── config.json              # 本地配置文件（接口、模型、窗口设置，已在 .gitignore）
├── persona.json             # 本地角色人设文件（已在 .gitignore）
├── memory.json              # 本地长期事实记忆库（已在 .gitignore）
├── chat_history.json        # 本地对话历史记录（已在 .gitignore）
└── 1.png                    # 默认角色立绘素材
```

---

## 💡 常见问题 (FAQ)

**Q：点击透明空白区域时无法穿透到后面的窗口？**
- A：AsaPet 内置了基于 Windows 原生扩展样式的实时穿透引擎，当鼠标位于角色透明区域时会自动对点击放行；请确保不要以管理员权限运行桌宠去穿透非管理员窗口（UIPI 限制）。

**Q：为什么提示获取模型列表失败？**
- A：请检查 Base URL 是否正确填写（末尾不要多余斜杠，如 `https://api.deepseek.com/v1`），API Key 是否有效。部分中转平台如果不开放 `/models` 端点，也可以直接在下拉框中手动输入模型名称。

**Q：聊天对话会有隐私泄露风险吗？**
- A：所有对话历史（`chat_history.json`）、长期事实记忆（`memory.json`）、API 配置（`config.json`）均仅保存在本地当前目录，且都已加入 `.gitignore`，绝对不会被上传到公共 Git 仓库。

---

## 📜 鸣谢与许可

- [live2d-py](https://github.com/Arkueid/live2d-py)：非官方 Python Live2D 绑定库
- [PySide6 / Qt](https://wiki.qt.io/Qt_for_Python)：图形界面与底层网络支持
- 角色模型版权归原制作方所有，本项目代码遵循 MIT 许可证开放。
