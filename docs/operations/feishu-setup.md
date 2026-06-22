# 飞书配置

在 [飞书开放平台](https://open.feishu.cn/app) 创建自建应用，配置四处。

## 1. 权限

应用详情 → 权限管理 → **导入权限配置**，粘贴以下 JSON：

```json
{
  "scopes": {
    "tenant": [
      "im:chat",
      "im:chat.access_event.bot_p2p_chat:read",
      "im:chat.members:bot_access",
      "im:chat:readonly",
      "im:message",
      "im:message.group_at_msg.include_bot:readonly",
      "im:message.group_at_msg:readonly",
      "im:message.group_msg",
      "im:message.p2p_msg:readonly",
      "im:message.reactions:write_only",
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:resource"
    ]
  }
}
```

> 只含数字生命实际需要的权限。`im:message.reactions:write_only` 是可选的表情收条。

## 2. 事件订阅

应用详情 → 事件与回调 → 选「长连接」（不需公网回调地址）→ 开启 `im.message.receive_v1`。

## 3. 机器人

应用详情 → 应用功能 → 启用机器人。

## 4. 发布 + 加群

创建版本并发布。把 bot 加进测试群（或私聊 bot 发消息）。

## 填入实例

实例 Config → 飞书 → 填 App ID + App Secret → 重启。
