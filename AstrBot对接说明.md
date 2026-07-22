# 桌宠 ↔ AstrBot（跨机器版）对接说明

## 你的架构

```
QQ 服务器 ←→ NapCat（在AstrBot主机上）─┐
                                       ├─→ AstrBot ─→ LLM
桌宠（本地）─────── OneBot 反向 WS ─────┘
```

桌宠作为一个 **OneBot v11 客户端**，跟 NapCat 平级，一起连到 AstrBot 已经在监听的**反向 WS 端点**。这样：

- 你在桌宠输入框里发消息 → AstrBot 处理（用它的人格 + 记忆）→ 回复显示在桌宠气泡里
- **完全不经过 QQ**，也**不影响** NapCat 那个 QQ 账号
- 记忆由 AstrBot 自己管，下次开桌宠继续聊

## 前提

你在 AstrBot 里的 aiocqhttp 平台已经是**反向 WS 模式**（NapCat 就是这么连过去的）。桌宠会连到**同一个端点**，用不同的 `self_id` 区分。

假设你 AstrBot 主机的 aiocqhttp 反向 WS 端点是 `ws://<AstrBot主机IP>:6700`（AstrBot 默认就是 6700，如果你改过端口就用你自己的）。

---

## 桌宠端配置

### 方法 1：右键菜单里改

1. 启动 `dist\KanadePet.exe`
2. **右键桌宠 → AstrBot 连接设置…**
3. 填写：
   - **WS 地址**：`ws://<AstrBot主机IP>:6700`（改成你的实际 IP 和端口）
   - **Access Token**：如果 AstrBot 那边配了就填，否则留空
   - **Bot QQ 号**：随便一个数字，**不能和 NapCat 的那个 QQ 号相同**，比如 `10001`
   - **用户 QQ 号**：桌宠里"你"的 ID，随便一个数字，比如 `20001`。这个 ID 决定了 AstrBot 会把桌宠里的对话当作**同一个用户**的连续对话（用于记忆隔离）
4. 点确定，自动重连

### 方法 2：直接编辑配置文件

配置文件在 exe 同目录下的 `config.json`：

```json
{
  "ws_url": "ws://192.168.1.10:6700",
  "access_token": "",
  "self_id": "10001",
  "user_id": "20001",
  "nickname": "主人"
}
```

---

## AstrBot 端要做什么？

**通常什么都不用做**。因为 NapCat 已经在成功连了，说明反向 WS 端点在监听着。桌宠只是"另一个 OneBot 客户端"，直接连过去就行。

如果 AstrBot 那边对**同一个平台配置**只允许一个连接，你可以选择：

- **选项 A（推荐）**：在 AstrBot 平台管理里**再新增一个 aiocqhttp 平台**（比如叫 KanadePet），配同样的反向 WS 端口，桌宠专用。可以给它绑不同的人格（比如就叫"宵崎奏"）。
- **选项 B**：直接和 NapCat 共用同一个平台。桌宠里的 `self_id` 与 NapCat 不同即可，AstrBot 会把它们当作两个不同的 bot 账号，各自维护会话。

---

## 使用

1. 启动桌宠
2. **右键 → 和奏聊天…** → 弹出输入框
3. 输入 → 回车 → 回复出现在头顶气泡里
4. 右键菜单能看到"已连接 / 未连接"状态
5. 断线会自动每 5 秒重试

---

## 常见问题

**Q：菜单一直显示"未连接"**
A：检查
- WS 地址是不是能从桌宠机器 ping 通 AstrBot 主机
- 端口对不对（AstrBot 那边看下 aiocqhttp 反向 WS 监听的端口）
- 防火墙有没有放行
- 如果 AstrBot 有 token，桌宠这边也要填对

**Q：AstrBot 说"self_id 冲突"或者顶掉了 NapCat**
A：把桌宠的 Bot QQ 号改成一个 NapCat 没用的数字。

**Q：想改人格**
A：在 AstrBot 里给这个连接绑定一个新的 Persona，配好 prompt。或者按上面"选项 A"新增一个专属桌宠的平台。

**Q：会不会影响 QQ 上的 bot？**
A：不会。桌宠是独立的连接和会话，你 QQ 里的 bot 依然正常工作。
