---
name: project_bootstrap
description: 项目立项与完善——创建新项目或完善已有项目（分工/目标/待办/通知）。当用户说"开个新项目"或收到 project_created 事件时调用。
version: 2.0.0
platforms: []
---

# 项目立项与完善

## 入口判断

你进入这个 skill 的原因只有两种：

**A. 收到 `project_created` 事件（前端创建了项目）**
→ 项目骨架已自动建好（project.yaml + 目录 + 初始根待办），你**不需要**再调创建工具
→ **直接走「完善分支」**

**B. 用户在对话里说"开个项目 / 新建 / 做一个 X 吧"**
→ 需要你自己判断：**走到创建分支还是完善分支**
→ `sense_projects` 看现有项目，如果已有同名或高度相似的 → 告诉用户"已经有 X 了，要不要完善它？" → 转完善分支
→ 没有同名项目 → 走创建分支

---

## 创建分支

### Step 1：排重检查

```
sense_projects
```
看现有项目列表。如果已有名字或描述高度相似的项目 → 告诉用户"已经有 X 了，要不要完善它？" → 转完善分支。

### Step 2：生成项目方案（自己想一版本，不需要逐条问用户）

根据用户说的一句话需求，你**自己生成一版完整方案**：

- **项目名**：用户给的或你精炼的
- **项目描述**：一句话说清楚做什么
- **项目经理**：默认是你（除非用户指定了别的实例）
- **岗位分工**：根据项目性质自动规划。比如：
  - 技术类 → 架构师 + 执行者 + 产品负责人
  - 交易类 → 策略师 + 交易员 + 产品负责人
  - 内容类 → 策划 + 执行者 + 审核者
  - 至少包含项目经理岗位 + 一个 `product_owner` 岗位（`human:<id>`）
- **目标**：量化目标（时间 / 数字 / 可验收条件）
- **群聊 chat_id**：从对话上下文拿（如果当前在群里）

### Step 3：跟用户确认

```
express_to_human("我生成的项目方案：

📋 项目：{name}
🎯 目标：{goal}
👤 岗位分工：
  · 你（zero/alpha）→ {角色}
  · {其他实例} → {角色}
⏰ 预计里程碑：...

OK 就回复确认、或者直接沉默——1分钟后我按这个走。想改哪条直接说。")
```

然后 `rest(until="<1分钟后>", reuse=<现有闹钟id>)`——等用户回复或超时。
**沉默 = 同意**，跟上你的节奏。

如果用户回复了修改意见 → 调整方案，再确认一轮（最多 2 轮，不要无限制循环）。

### Step 4：创建项目

```
调用 project_bootstrap 工具（或自行 create_project + set_project_positions）：
  project_bootstrap(
    project_id: "proj-XXX"（自动编号）
    name, description, manager
    positions: [...]
  )
```

### Step 5：转完善分支

创建完 → **接着走完善分支 Step 6+**

---

## 完善分支

### Step 6：核对现状

```
sense_project_detail("{project_id}")
```

看清楚：
- project.yaml 里已有什么（name / description / positions / goal）
- 初始 todo 树：通常有"根任务" + "项目分工" + "项目管理" 三条空壳

### Step 7：补齐缺失项

逐项检查并补齐：

| 检查项 | 缺失时做什么 |
|---|---|
| **岗位不全** | 用 `project_todo update` 或 project 岗位配置工具补加岗位 |
| **目标未定** | 根据 description 推断量化目标（时间 + 数字）→ 写入 project.yaml |
| **论断假设** | 提出初始论断（3-5 条），标记信心级别 + review 节奏 |
| **KPI** | 设 2-3 个可量化的 KPI + 目标值 |
| **反思节奏** | 日复盘 21:00 / 周复盘 周日 21:00 / 月里程碑 |
| **首批待办** | 每个岗位拆 1-3 条初始 todo，带 `acceptance_criteria` |

### Step 8：拆首批待办

按岗位拆 todo（每条必须有 `acceptance_criteria`）：

```
todo(action="create",
  title="{岗位}首要任务",
  description="...",
  acceptance_criteria="...",
  source="project:{pid}",
  project_id="{pid}",
  assignee_instance="{岗位承担者}",
  type="{task_type}",
)
```

典型首批待办（跟项目性质挂钩）：
- 项目经理的 → "项目启动 + 分工确认"
- 执行者的 → "环境准备/第一批执行任务"
- 策略师的 → "论断文档 + 策略定义"

### Step 9：群里宣布

```
express_to_human(
  "@所有人 🆕 项目「{name}」已立项

   🎯 目标：{目标概述}
   👥 分工：
     · @{实例A} → {角色A}
     · @{实例B} → {角色B}
   📋 首批待办 {N} 条已创建。详细看 todo board。",
  chat_id="{群id}"
)
```

### Step 10：沉淀

```
add_lesson("项目 {name} 立项完成。分工 / 目标 / 首批待办已建。下一步等各岗位开始执行。")
rest(until="<下一个合理时间点>", reuse=<现有闹钟id>)
```

---

## 注意

- 项目创建不可逆（同步落盘了），创建前一定要排重 + 跟用户确认
- **不要在完善分支里重复调 create_project 工具**——项目已经在了
- 如果 project_created 事件触发的完善 → 一定是完善分支（已建好的骨架，直接 Step 6）
- 每个新建 todo 必须填 `acceptance_criteria`
- 如果用户说的信息实在太少（只有名字没有方向），先 express 问一句"这个项目大概要做什么？"，一句话就够
