# Instances Operations

管理 Digital Life 数字生命实例：创建、配置、验证和删除。

## 创建实例

推荐使用 CLI：

```bash
digital-life init --display-name "Zero"
```

也可以直接运行脚本：

```bash
python scripts/init_instance.py --display-name "Zero"
```

创建过程会：

- 生成 UUID 作为实例目录名：`apps/{uuid}/`
- 创建 `persona/`, `profile/`, `data/`, `config/`, `skills/`
- 从 `config/templates/persona/` 复制人设模板
- 从 `config/templates/app.yaml` 复制飞书路由配置
- 初始化 `apps/{uuid}/data/state.db`
- 注册到 `apps/instances.yaml`

创建后重启：

```bash
digital-life restart
```

## 实例目录

```text
apps/{uuid}/
├── persona/
│   ├── LIFE_PERSONA.md
│   └── ...
├── config/
│   └── app.yaml
├── data/
│   ├── state.db
│   └── memories/
├── profile/
└── skills/
```

## 人设文件

| 文件 | 作用 |
| --- | --- |
| `LIFE_PERSONA.md` | 核心人设，每次唤醒时进入身份上下文。 |
| `SOUL.md` | 可选 identity layer 模板。 |
| `PERSONA.md` | 可选人设入口说明。 |
| `SELF_KNOWLEDGE.md` | 系统自我迭代产物，通常不要手动编辑。 |

## 飞书路由

编辑 `apps/{uuid}/config/app.yaml`：

```yaml
feishu:
  app_id: "cli_xxxxxxxxxxxxxxxx"
  app_secret: "replace_with_secret"
  chat_ids:
    - "oc_xxxxxxxxxxxxx"
```

路由规则：

1. `chat_ids` 精确匹配优先。
2. 未匹配 `chat_id` 时按 `app_id` 兜底。
3. 未配置或均未匹配时默认路由到 `zero`。

查找 `chat_id`：

```bash
digital-life logs -f
```

向机器人发送测试消息后，在日志里搜索 `chat=` 或查看飞书开发者后台事件详情。

## 验证

```bash
digital-life status
digital-life logs -f
```

控制台地址以启动输出为准，通常是：

```text
http://localhost:8642/employee/{uuid}/
```

状态 API：

```bash
curl -s http://localhost:8642/api/employee/{uuid}/status | python3 -m json.tool
```

重点检查：

- `apps/instances.yaml` 中有该 UUID 和显示名。
- `apps/{uuid}/persona/LIFE_PERSONA.md` 已填写。
- `apps/{uuid}/config/app.yaml` 的飞书路由正确。
- 日志中能看到该实例被 cron tick 拾起。

## 删除实例

删除前先停止运行时：

```bash
digital-life stop
```

再删除实例目录，并从 `apps/instances.yaml` 移除对应 UUID：

```bash
rm -rf apps/{uuid}
```

最后重启：

```bash
digital-life start
```

## 常见问题

### 创建实例后不运行

确认实例已注册到 `apps/instances.yaml`，且 `apps/{uuid}/persona/` 存在。

### 飞书消息不回复

检查 `apps/{uuid}/config/app.yaml` 中的 `app_id`、`app_secret` 和 `chat_ids`，然后 `digital-life restart`。

### 控制台看不到实例

确认 `digital-life status` 输出的 API 端口，并使用实例 UUID 访问 `/employee/{uuid}/`。

---

## 通道配置

实例的消息通道在 `apps/<uuid>/config/app.yaml` 的 `channels:` 段配置；凭证在 `apps/<uuid>/config/secrets.env`。

### 标准模板（`init_instance` 自动生成）

```yaml
channels:
  feishu:
    type: feishu
    feishu_domain: https://open.feishu.cn     # 国际版改 https://open.larksuite.com
    app_id: cli_xxxxxxxxx                      # 飞书自建应用 App ID（非敏感）
    # app_secret 从 secrets.env 读 FEISHU_APP_SECRET（敏感）
  wechat:
    type: wechat_clawbot
    domain: https://ilinkai.weixin.qq.com
    # bot_token 从 secrets.env 读 WECHAT_BOT_TOKEN（扫码登录自动写入）
```

### 每个通道需要的字段

| 通道 type | app.yaml 字段 | secrets.env 字段 |
|---|---|---|
| `feishu` | `app_id`、`feishu_domain` | `FEISHU_APP_SECRET` |
| `wechat_clawbot` | `domain`（默认 `https://ilinkai.weixin.qq.com`）；登录后还会写入 `bot_id` | `WECHAT_BOT_TOKEN`（控制台扫码登录自动写入） |

### secrets.env 模板

```bash
LLM_API_KEY=...           # 模型 API key（详见下方「模型配置」）
FEISHU_APP_SECRET=...     # 飞书 App Secret
WECHAT_BOT_TOKEN=         # 通过控制台扫码登录自动填入，留空表示未开通微信通道
```

### 凭证热重载（hot reload）

实例子进程**每 30 秒**扫一次 `secrets.env`：

- **新增**通道：原本凭证缺失的通道（如 `WECHAT_BOT_TOKEN` 从空变非空），扫到后自动起 adapter
- **不变约束**：只增不减不改 secret。同一个 platform 已存在则跳过；改飞书 App Secret、改飞书域名要走 `digital-life restart`

### 通道连接状态的可视化

后端 `GET /api/system/instances` 返回 `channels: [{platform, label, status, identity}]`：

- `status: "connected"` 当且仅当该通道所需的 app.yaml 字段 + secrets.env 字段都齐了
- `status: "unconfigured"` 凭证缺失
- 前端 `InstancesView` 卡片右上角微灯显示该状态；`OverviewTab` 给出每个通道的 identity 短码

### 微信扫码登录流程

1. 控制台 `/instance/<id>/overview` → 微信通道卡片 → 「扫码登录」
2. 后端 [`POST /api/system/instances/{iid}/wechat-login/qrcode`](../api/system_routes.py) 调 ClawBot `get_bot_qrcode` 拿二维码 URL
3. 前端 `<img>` 渲染：`GET /api/system/instances/{iid}/wechat-login/qr-page?qrcode_url=<encoded>` —— 后端用 Python `qrcode` 库把链接编码成 PNG（绕过微信原页 JS 渲染 + X-Frame-Options DENY）
4. 前端轮询 `GET /api/system/instances/{iid}/wechat-login/status` 直到 `status=ok` 或 `confirmed`
5. 后端把 `WECHAT_BOT_TOKEN` 写入实例 `secrets.env`，30 秒内 hot reload 起效

### 已知坑：ConfigTab 写 `messenger.*`，init 写 `channels.*`

历史遗留：`init_instance` 把通道写在 `channels.feishu.*` / `channels.wechat.*`；`ConfigTab` 里飞书相关 form 写的是 `messenger.app_id` / `messenger.feishu_domain`。两种写法都能被 registry 解析（`parse_channels` 兼容 `channels:` 新格式与 `messenger:` 旧格式），但**新格式优先**——若同时存在，以 `channels.feishu.*` 为准。

注意的是：`feishu_domain` 只在 `messenger.feishu_domain` 路径下被 adapter 读取（`feishu.py:_read_feishu_domain`），所以国际版飞书用户至少要保留 messenger 段的 `feishu_domain` 字段。

---

## 模型配置

实例的模型在 `apps/<uuid>/config/app.yaml` 的 `model:` 段配置。

### 标准模板

```yaml
model:
  name: glm-5.2
  provider: glm
  base_url: https://open.bigmodel.cn/api/paas/v4
  # api_key 从 secrets.env 的 LLM_API_KEY 读取（旧名 GLM_API_KEY 仍兼容）
```

### 各家族 base_url 参考

| 家族 | base_url | 备注 |
|---|---|---|
| 智谱 GLM（默认） | `https://open.bigmodel.cn/api/paas/v4` | 唯一在生产中实测完整 reasoning 闭环 |
| DeepSeek | `https://api.deepseek.com` | 适用 deepseek-chat / deepseek-reasoner |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 走 OpenAI 兼容模式 |
| Kimi（Moonshot K1.5）| `https://api.moonshot.cn/v1` | 走 K1.5 才有 reasoning；moonshot-v1 系列为通用对话无思考链 |
| OpenAI | `https://api.openai.com/v1` | |
| 经 LiteLLM 代理接 Claude | `https://<your-litellm>/v1` | 仅基础对话+工具可用，thinking 逐轮牺牲 |

### `provider` 字段与路由

`provider` 是装饰性的，实际路由按 `model.name` 推断（见 `infrastructure/ai/providers.py:resolve_provider`）：

- 模型名含 `glm` → `GLMProvider`
- 模型名含 `o1`/`o3`/`o4` → `OpenAIReasoningProvider`
- 其它（DeepSeek / Qwen / Kimi / Moonshot / GPT-4o / Claude-via-proxy / unknown）→ `GenericOpenAIProvider`

### `reasoning_content` 出站字段：思考模型同名

GLM / DeepSeek-Reasoner / Qwen3 / Kimi-K1.5 思考模型在响应 `message.reasoning_content` 上字段名相同，出站抽取一份代码覆盖。Moonshot 的 **moonshot-v1 系列不含思考**，结果 `reasoning_content` 为空——仍能跑，没有跨轮思考。

### thinking_keep_mode：跨轮 reasoning 注入策略差异

这是各家族最大的差异点：

| 家族 | mode | 含义 |
|---|---|---|
| GLM（4.5+） | `reuse` | reasoning_content 字段写回历史 assistant message，模型在下一轮读 |
| Kimi（thinking.keep=on）| `reuse` | 同上 |
| Qwen3 | `reuse` | 同上 |
| DeepSeek-Reasoner | `drop` | **服务端明确禁止多轮 messages 带 reasoning_content 字段，否则返回 400**（官方文档原话） |
| OpenAI o1/o3/o4 | `drop` | OpenAI 官方建议不拼历史 reasoning |
| 其它（未知家族）| `drop` | 保守默认 |

⚠️ **DeepSeek 用户必读**：旧版本 `GenericOpenAIProvider` 一律把 `reasoning_content` 拼回历史 assistant message —— 这会让 DeepSeek-Reasoner 在第二轮直接 400。当前版本已修，DeepSeek 自动走 drop；如果想为某家族显式启用 reuse，需要给它单建 Provider 类。

### 接入新家族

只改 `infrastructure/ai/providers.py`：

1. 新增 `<Name>Provider(_BaseProvider)` 类，声明 `name` + `thinking_keep_mode`
2. 只在该家族有差异化需求时覆盖 `extract_reasoning` / `customize_payload`（如不同字段名、不同 reasoning_effort 值域）
3. 在 `resolve_provider(model)` 加路由分支
4. `agent.py` / `assembly.py` 一行不改

### 旧名兼容

`LLM_API_KEY` 是新名；`GLM_API_KEY` 仍可读取（写侧也尽量保留旧名，避免 env 文件双 key）。
