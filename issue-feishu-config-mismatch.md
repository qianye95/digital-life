# 飞书 App ID 配置路径不一致，前端保存后通道不生效

## 问题描述

在前端配置页面（Config）填写飞书 App ID 后保存，配置值写入了 `messenger.app_id`，但飞书 ingress adapter 实际读取的是 `channels.feishu.app_id`。两个路径不一致，导致前端保存的 App ID 对通道永远不生效，飞书适配器始终使用模板中的占位符 `cli_xxxxxxxxx`。

## 复现步骤

1. `digital-life init` 初始化实例（或手动创建）
2. 在前端 Config 页面的"飞书通道"section 填写飞书 App ID（如 `cli_aad8b946ea785bfb`）并保存
3. 重启网关
4. 查看实例日志，发现 adapter identity 仍是占位符

```
[interfaces.ingress.feishu_streaming_adapter] INFO FeishuStreamingAdapter created (enable_streaming=False)
[Lark] ERROR connect failed, err: 1000040346: app_id is invalid
```

## 根因分析

### 配置写入路径

前端 ConfigCenter 定义的飞书 App ID 字段（`application/console/config_center.py`）：

```python
ConfigField(
    "messenger.app_id", "飞书 App ID", "feishu", "yaml", path="messenger.app_id",
    description="飞书自建应用 App ID（cli_xxx）。",
)
```

→ 前端保存时，值写入 yaml 的 `messenger.app_id`

### 通道读取路径

`init_instance` 生成的模板（`infrastructure/bootstrap/instance.py`）中，`channels.feishu.app_id` 和 `messenger.app_id` 是两个独立字段，各自持有占位符：

```yaml
channels:
  feishu:
    type: feishu
    app_id: cli_xxxxxxxxx      # ← adapter 读这个
    feishu_domain: https://open.feishu.cn
messenger:
  type: feishu
  app_id: cli_xxxxxxxxx        # ← 前端写这个
```

`interfaces/ingress/registry.py` 的 adapter 工厂 `_build_feishu()` 从 `cfg.get("app_id")` 读取，此时 `cfg` 是 `channels.feishu` 段的内容，所以读到的是 `channels.feishu.app_id`。

### 合并逻辑的缺陷

`registry.py` 中 `parse_channels()` 的合并策略是"channels 优先，不覆盖"：

```python
# 1. 新格式 channels 段
raw_channels = app_yaml_cfg.get("channels")
if isinstance(raw_channels, dict):
    channels.update(raw_channels)
# 2. 旧格式 messenger 段 → 补充为 feishu channel（不覆盖已有的 channels.feishu）
messenger = app_yaml_cfg.get("messenger")
if isinstance(messenger, dict) and messenger:
    msgr_type = str(messenger.get("type") or "feishu")
    if msgr_type not in channels:
        channels[msgr_type] = messenger
```

因为 `channels.feishu` 已经存在（虽然 app_id 是占位符），`messenger` 段不会被补进去，`messenger.app_id` 的正确值永远无法传递到 adapter。

## 影响范围

- 所有通过前端 Config 页面配置飞书 App ID 的用户
- `init_instance` 生成的新实例必定复现（模板里两个路径都是占位符）
- 手动编辑 `channels.feishu.app_id` 可以绕过，但前端配置页面无此入口

## 修复建议

### 方案 A（推荐）：ConfigCenter 同步写入两个路径

在 `ConfigCenterWorkflow.update_config()` 中，当 `messenger.app_id` 被更新时，同步写入 `channels.feishu.app_id`：

```python
if "messenger.app_id" in yaml_updates:
    yaml_updates["channels.feishu.app_id"] = yaml_updates["messenger.app_id"]
```

### 方案 B：ConfigCenter 直接改为配置 channels.feishu.app_id

将 ConfigField 的 path 改为 `channels.feishu.app_id`，与 adapter 读取路径一致。

### 方案 C：registry 合并时做 fallback

在 `parse_channels()` 中，当 `channels.feishu.app_id` 是占位符或空串时，用 `messenger.app_id` 覆盖。

## 环境信息

- digital-life 版本：0.1.0
- Python：3.11
- 操作系统：macOS
