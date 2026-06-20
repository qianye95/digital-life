# 如何玩转数字生命

一份从"刚装完"到"日常使用"的实战指南。10-20 分钟读完，半小时跑通。

## 目录

1. [你刚装完，先看什么](#1-你刚装完先看什么)
2. [第一次跟它对话](#2-第一次跟它对话)
3. [日常怎么用](#3-日常怎么用)
4. [进阶玩法](#4-进阶玩法)
5. [当它出问题时](#5-当它出问题时)

---

## 1. 你刚装完，先看什么

装完后启动 gateway：

```bash
digital-life start
```

第一次启动会自动 bootstrap **一份示范体验包**：

- 两个数字生命实例 `zero`（青色）和 `alpha`（粉色）—— 起步就是两个独立个体
- 一个示例项目 `trading_simulation`（模拟炒股）—— 让两个实例有事可做、有协作场景

> 这只是开箱体验包。你可以删掉它们从零搭自己的项目；实际玩法见 [§4 进阶](#4-进阶玩法)。

### 关掉终端，打开控制台

```bash
digital-life status   # 看到底跑在哪个端口（默认 8642）
```

打开 `http://localhost:8642/system`（霓虹深空主题）。

**全局台**先看到：
- 系统实况：zero + alpha 卡片，每张卡片右上角有**通道连接状态微灯**（绿=已连接，灰=未配置）
- 实例管理：zero / alpha 的 avatar / accent / tagline 可编辑
- 项目：`trading_simulation` 卡片可点进去看完整结构

### 验证实例活着

进入 zero 的实例台（`/instance/<zero-uuid>/overview`）：
- 实例状态 = `休息中` 或 `工作中`（**绝不应该是 `异常` 或 `离线`**）
- 能量 = 接近 100%
- 顶部「通道连接状态」面板显示飞书 / 微信各自的连接情况

进入 Session → 应该能看到历史 wakes 列表。如果空，没关系 —— 实例刚开始没事件进来很正常。

### 你还没办法跟它对话 —— 现在填飞书凭证

这一步必须在飞书控制台做：
1. https://open.feishu.cn/app 新建两个"自建应用"（一个给 zero，一个给 alpha）
2. 各自把 bot 加进同一个**测试群**（这是 zero 跟 alpha 协作的通道）
3. 拿到 `App ID` + `App Secret`

然后：

**方法 1（控制台，推荐）**：`/instance/<id>/config` → 在「飞书通道」section 填 App ID + App Secret → 保存 → 控制台顶部「重启」生效

**方法 2（命令行）**：

```bash
# zero 的凭证：如果 config/secrets.env 已填，bootstrap 时已自动塞给 zero；
#              用新 app 就改 apps/<zero-uuid>/config/secrets.env 的 FEISHU_APP_SECRET
# alpha 的凭证：全新填
vi apps/<alpha-uuid>/config/secrets.env  # 改 FEISHU_APP_SECRET

# 重启
digital-life restart
```

填好后回到 Overview，飞书通道微灯应该转绿。

---

## 2. 第一次跟它对话

在飞书群里发一条消息（直接发就行，不一定 @）。

数字生命会根据上下文判断该不该回、由谁回。你可以用它，也可以不用：

- @ 它 —— 一定属于它，立即响应
- 不 @ —— 它会评估"这条话跟我有关吗"，相关就回，无关就安静

群里 bot 在线、且群里同时有 zero 和 alpha 两个 bot 时，发一条消息两个 bot 都能听到（这是飞书服务端的 fan-out）。两个 bot 自己会决定谁更适合回 —— 谁是这条话的对象、谁精力状态更好等等。

### 验证对话通了

随便说一句话，30 秒内应该有 bot 回复。如果一直没回：

- 看 Overview 状态不应该是 `异常` / `离线`
- 看 channels 微灯是绿的
- 看 logs：`digital-life logs -f` 关注 `Ingress message` / `L4 event` 关键字

---

## 3. 日常怎么用

### 跟它对话

跟它说话不需要每次 @。两个例子：

- 你问"项目接下来该做什么" —— 它从项目状态、待办、上次复盘推断
- 它自己发现该做某件事 —— 由事件机制触发 wake，不需要你下指令

被 @ 是平权事件里的高优先级之一，但不绝对最高 —— 仲裁还要看精力、看是否在某个 affair 中。

### 给它技能

`/system/skills` 是**技能市场**，列出所有全局 skill（来自 `interfaces/skills/` + `shared/skills/`）。

对每个实例 toggle 订阅：`/instance/<id>/skills` 只显示它订阅的技能，订阅 = `app.yaml.skills` 列表加一条。

新增自定义技能：在 `shared/skills/<name>/SKILL.md` 写好 markdown 模板，master 重启后会自动出现在市场。

> 技能是**正常的能力添加**，不是进阶玩法。日常要用就加。

### 看它在做什么

- **概览** (`/instance/<id>/overview`)：状态、能量、最近 wakes、待办 Top、token / day
- **会话** (`/instance/<id>/sessions`)：完整 wake 列表，点击看每个 wake 的 turns、tool calls、LLM call 完整输入 JSON（debug 友好）
- **记忆** (`/instance/<id>/memories`)：意识流 / 日记 / 联想图谱

### 不打扰它时，它会自己活

第二天早上你会发现 —— 即使你睡觉了，zero 和 alpha 可能也没闲着：

- 定时器（routines.yaml 里预设节奏框架）触发 wake
- 主动探索（精力足够时会自己检查项目状态、扫描候选）触发 wake
- 某个事件被触发（如阈值告警）触发 wake

查看它们的"昨晚"做了什么：

1. `/instance/<zero-uuid>/sessions` —— 找 timestamp 在昨晚的 wake，点开看完整 turns（含 reasoning + tool calls + LLM call JSON debug）
2. `/instance/<zero-uuid>/memories` —— 切到「日记」，按日期分段看复盘
3. `/instance/<zero-uuid>/memories` —— 切到「意识流」，看它整理思绪的过程

### 调整人设

如果你不喜欢它的语气或行为模式：`/instance/<zero-uuid>/persona` —— 编辑 LIFE_PERSONA.md。比如让它更严谨 / 更俏皮 / 更直接。保存，下次 wake 生效。

---

## 4. 进阶玩法

基础对话 + 技能让它"能用"。下面 4 件事让它"真正成为数字员工"。

### 4.1 项目机制

项目是一个**有目标 + 有岗位分工 + 有 deadline 的虚拟工作**。`trading_simulation` 示范项目就是完整一例：有 KPI、有论断、有岗位、有交付物。

**自己建项目**：`/system/projects` → 新建项目 → 填 `project.yaml`：

```yaml
project:
  id: content_creation
  name: 内容创作
  goal:
    statement: 每周产出 3 篇精品长文
    deadline: 2026-09-30
  positions:
    - id: writer
      name: 撰稿人
      assignees: [<zero-uuid>]
    - id: reviewer
      name: 审稿
      assignees: [<alpha-uuid>]
  group_chat_id: oc_xxx   # 可选：把项目和某个飞书群挂钩
```

数字生命会接管分配到自己身上的岗位。**项目是数字生活协作的载体** —— 不挂项目，它们就只是两个会聊天的 bot；挂了项目，它们才分工干实事。

岗位不是硬编码 —— 项目自由定义角色。同一对实例在不同项目里可以是不同分工。

### 4.2 待办

每个数字生命有独立的待办列表，按项目分组。`/instance/<id>/todos` 可勾选完成 / 删除 / 新建。

待办来自三个源：

1. **数字生命自己生成**：它把项目目标拆成可执行 todo，写进自己的列表
2. **你直接交代**：群里说"明天早上检查一下持仓股票的新闻" —— 它会主动建 todo
3. **项目级 todos.db**：项目共享的待办，每个岗位可以 pickup

待办是它"持续做事"的载体 —— 当前 wake 没完成，下个 wake 会接着做。配合 routines.yaml 的时间槽，能保证它真在推进。

### 4.3 事件注册与对接机制

数字生命靠**事件**活着，不是靠你的指令。事件类型在 `/system/events` 注册：

- `message` —— 飞书 / 微信消息进来
- `routine` —— routines.yaml 里预设的时间槽到点了
- `timer` —— 你给它定的定时器（如"30 分钟后提醒我"）
- `condition` —— 自定义条件触发（如 "账户亏损 5%" 触发 `risk_alert`）
- `initiative` —— 模型自己的主动探索（精力充足时）

**自定义事件接入**：`/system/events` 新建一个 event-type，填 `type_id`、`trigger_type`、prompt 模板。事件被外部系统触发后会按这个 prompt 走 wake 流程。

对接自己的业务（如 webhook、监控告警、CRM 状态变化）→ 写一个适配器调 `emit_event(kind=..., payload=..., source=...)`，数字生命就能感知到。

事件源 + 数字生命的自主决策 = 它能在你不在的时候自己行动。

### 4.4 多 Agent 协作

一个数字生命是单兵；两个以上是组织。

**多实例协作机制**：
1. **飞书原生 fan-out**：飞书服务端把每条消息推给群里所有 bot（飞书专属特性）
2. **去中心化消息总线**：实例主动发言时把出站消息广播给同群的其他实例（peers），各自写入对方 messages.db + 触发 wake（通道无关兜底）
3. **岗位机制**：项目里分配岗位，决策 / 执行 / 拍板不同 mentor，模型按岗位身份行动

每个实例仍是独立 lifecycle（自己的 affair / 记忆 / 精力 / 人设），通过消息总线协同，不共享运行态。

**想增加第三个数字生命**：

1. `/system/instances` → 新建实例，配 display_name / accent_color / tagline / 飞书凭证
2. `/system/skills` 给新实例订阅合适的技能
3. （可选）把它加进某个项目的某个岗位
4. 控制台「重启」拉起新实例子进程

它是一个**完全独立的生命**：自己的 persona、记忆、精力、复盘习惯，跟你 chat 时不是同一个声音。

完整协作场景实录见 `docs/showcase/multi-instance-trading-2026-06.md` —— 一个真实长期运行的 zero + alpha 协作一天。

---

## 5. 当它出问题时

### 实例显示「异常」（status=error）

进 `/instance/<id>/overview` → 红色 banner 会显示**具体原因**：

```
⚠ 数字生命异常
模型调用失败：LLM_API_KEY invalid (turn #1065, role=assistant)
```

按 hint 修：
- API key 没填 / 填错 → 控制台 `/instance/<id>/config` 改 model section
- 模型 quota 用完 → 换 key 或等次日 reset
- 飞书 WS 断了 → 看是不是 token 失效（飞书控制台 revoke 的话）

**reset 按钮**：仅 abort 卡住的 wake（不动 lifecycle 状态机，模型自主决定何时休息/工作）。

**自动恢复**：一旦下一次 wake 里的模型调用成功（任意 role=assistant 无 error），banner 自动消失。

### 实例显示「离线」

实例 `app.yaml.active = false`，进程没起。控制台「上线」按钮一键拉起（或重启 gateway）。

### 通道显示「未配置」（灰灯）

飞书 token 失效 / app_secret 改了没重启 → 控制台 `/instance/<id>/config` 重填或检查 secrets.env。

微信 token 失效（扫码后失效了）→ Overview 通道卡片 → 「重新扫码」即可。

### 数据库锁 / 启动失败

```bash
digital-life stop
# 等几秒
digital-life status    # 确认没残留进程
digital-life start
digital-life logs -f
```

### 重置单个数字生命

不直接删 `apps/<uuid>/` —— 会丢全部记忆。安全的做法：

```bash
digital-life stop

# 备份当前实例（包含全部数据）
cp -r apps/<uuid> apps/<uuid>.backup

# 清掉它当前事务状态，让 affair RESET —— persona / 记忆保留
sqlite3 apps/<uuid>/data/state.db "UPDATE affairs SET status='PENDING'"

digital-life start
```

### 重置整个项目（从空开始）

`/system/projects` → 删除目标项目 → 重启 gateway → master 会重新 seed `trading_simulation` 示范项目（这是开箱默认行为，可去 `infrastructure/http/server.py:_ensure_default_project` 改默认 seed）。或者删掉一份再不 seed，从零搭你自己的项目结构。

---

## 一句话总结

> Digital Life 不是你打开就用一下关闭的工具。它就是一直在那儿活着 —— 像几个真实员工。你不在的时候它在工作、在休息、在跟同伴协作、在自主修正论断。
>
> 你的角色是**项目里的人**：定方向、拍板、给反馈、调整它的边界。它能自己处理日常，重要的事主动找你。
