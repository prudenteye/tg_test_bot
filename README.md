# Telegram Bot Supabase 查询（Vercel Python Serverless）

本项目基于 Vercel Python Serverless 的 Telegram Bot。机器人接收用户文本，将其作为关键字在 Supabase/Postgres 数据库中进行包含匹配（ILIKE %q%）并返回结果。
- 输入长度限制：不超过 50 字节（UTF-8）
- 查询表：默认 accounts（可通过 SUPABASE_TABLE_NAME 覆盖）
- 查询列：默认 account（可通过 SUPABASE_SEARCH_COLUMN 覆盖）
- 返回优先级：remarks → account_byte_length → 简要预览（含截断保护）

不再使用/读取任何本地 CSV 文件。

## 项目结构

```
.
├── api/
│   ├── webhook.py          # 主功能入口（/api/webhook）
│   └── requirements.txt    # 函数依赖（requests、psycopg[binary]）
├── index.html              # 入口页面（内置端点状态检测）
├── .env.example
├── .gitignore
├── .vercelignore
└── README.md
```

## 主功能入口与运行逻辑

- 入口文件：api/webhook.py
  - GET /api/webhook：健康检查，返回
    - bot_configured（是否配置了 Bot Token）
    - webhook_ok / webhook_url / webhook_error（Telegram Webhook 状态）
    - db_configured / db_driver_available / db_ok / db_error（数据库配置与连通性）
  - POST /api/webhook：处理 Telegram Webhook 更新
    - 仅处理文本消息（超过 50 字节会提示过长）
    - 调用 process_query(text) 执行数据库查询：
      - 通过 psycopg 连接至 DATABASE_URL（自动附加 sslmode=require）
      - 在 SUPABASE_TABLE_NAME 的 SUPABASE_SEARCH_COLUMN 上执行 ILIKE %q% 模糊查询，返回首条匹配

## 在 Vercel 上部署

1) 导入仓库
- 在 Vercel 中 New Project，选择本仓库创建项目（会自动识别 api/ 为 Serverless Functions）

2) 配置环境变量（Project Settings → Environment Variables）
- TELEGRAM_BOT_TOKEN（必填）：从 BotFather 获取的 Token
- DATABASE_URL（推荐）：Postgres 连接串，建议带 sslmode=require
  - 例：postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
- SUPABASE_TABLE_NAME（可选）：默认 accounts
- SUPABASE_SEARCH_COLUMN（可选）：默认 account

3) 构建与依赖
- Vercel 会基于 api/requirements.txt 自动安装依赖（requests、psycopg[binary]）
- 部署完成后访问 https://your-vercel-domain/api/webhook 验证健康检查
- 入口页 https://your-vercel-domain/ 会自动拉取 /api/webhook 的 JSON 并展示状态

4) 绑定 Telegram Webhook
- 设置 Webhook
  ```
  curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
    -d "url=https://your-vercel-domain/api/webhook"
  ```
- 查看 Webhook 状态
  ```
  curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
  ```

## 本地/联调使用

- 健康检查：
  ```
  curl -sS -o - -w "\nHTTP_STATUS:%{http_code}\n" https://your-vercel-domain/api/webhook
  ```
- 模拟 Telegram 消息（POST JSON）：
  ```
  curl -sS -o - -w "\nHTTP_STATUS:%{http_code}\n" \
    -X POST https://your-vercel-domain/api/webhook \
    -H "Content-Type: application/json" \
    -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":123,"type":"private"},"date":0,"text":"some-account"}}'
  ```

## 环境变量示例（参考）

参见 .env.example（示例文件，不会被 Vercel 直接读取；请在 Vercel 面板配置实际变量）：
- TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
- DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
- SUPABASE_TABLE_NAME=accounts
- SUPABASE_SEARCH_COLUMN=account

## 常见问题

- DB 无法连接：确认 DATABASE_URL 正确、网络可达、已启用 SSL（sslmode=require）
- 查询未命中：确认表名/列名与数据一致（仅支持字母/数字/下划线命名）
- Webhook 异常：在健康页或通过 getWebhookInfo 查看 last_error_message

## 许可证

MIT