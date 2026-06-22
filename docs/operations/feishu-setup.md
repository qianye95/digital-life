# 飞书配置

在 [飞书开放平台](https://open.feishu.cn/app) 创建自建应用，配置三处。

## 权限

应用详情 → 权限管理，搜索开通：

- `im:message`、`im:message:send_as_bot`、`im:message.p2p_msg:readonly`、`im:message.group_at_msg:readonly`、`im:chat`
- `im:message.reactions:write_only`（可选，消息加表情收条）

## 事件订阅

应用详情 → 事件与回调 → 选「长连接」（不需公网回调地址）→ 开启 `im.message.receive_v1`。

## 机器人

应用详情 → 应用功能 → 启用机器人。

## 发布 + 加群

创建版本并发布。把 bot 加进测试群。

## 填入实例

实例 Config → 飞书 → 填 App ID + App Secret → 重启。
