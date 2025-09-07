# Telegram Bot Supabase 查询（Vercel Python Serverless）

本项目基于 Vercel Python Serverless 的 Telegram Bot。机器人接收用户文本，在 Supabase/Postgres 数据库执行模糊匹配（ILIKE %q%）并返回结果摘要。

- 输入长度限制：不超过 50 字节（UTF-8）
- 查询表：默认 accounts（可通过 SUPABASE_TABLE_NAME 覆盖）
- 查询列：默认 account（可通过 SUPABASE_SEARCH_COLUMN 覆盖）
- 返回优先级：remarks → account_byte_length → 匹配提示

## 项目结构

```
.
├── api/
│   ├── webhook.py          # 业务层：处理 Telegram 更新（最小输出）
│   ├── conn.py             # 资源层：数据库连接与查询工具
│   └── requirements.txt    # 线上依赖（requests、psycopg[binary]）
├── index.html              # 入口页：仅检测端点与数据库状态
├── vercel.json             # Vercel 函数运行时与路由配置
├── .env.example
├── .gitignore
├── .vercelignore
└── README.md
```

## 运行逻辑（精简）

- GET /api/conn：健康检查
  - 响应 JSON：{"status":"ok","db_ok":true|false,"commit":{"sha":"xxxxxxx"}?}
- POST /api/webhook：处理 Telegram Webhook 更新
  - 仅处理文本消息（超过 50 字节会提示过长）
  - 通过数据库执行 ILIKE %q% 模糊查询；返回优先级：remarks → account_byte_length → 匹配提示

## 接口数据格式

- Telegram Webhook 输入（示例，关键字段）
  - message.chat.id: 会话 ID
  - message.text: 文本内容（字符串，≤50 字节）
- Bot 输出
  - 通过 Telegram sendMessage 发送文本到对应 chat.id
  - 接口自身返回 {"status":"ok"}，不回显查询细节
- 健康检查输出（最小化）
  - 字段：status, db_ok, commit.sha（可选）

## 在 Vercel 上部署

1) 导入仓库 → 新建项目（自动识别 api/ 为 Serverless Functions）
2) 配置环境变量（Project Settings → Environment Variables）
   - TELEGRAM_BOT_TOKEN（必填）
   - DATABASE_URL（推荐，Postgres 连接串，建议 sslmode=require）
   - SUPABASE_TABLE_NAME（可选，默认 accounts）
   - SUPABASE_SEARCH_COLUMN（可选，默认 account）
3) 构建与依赖
   - Vercel 自动安装 api/requirements.txt（requests、psycopg[binary]）
   - 部署完成后访问根路径查看 index.html 状态页；或 GET /api/webhook
4) 绑定 Telegram Webhook
   - 设置 Webhook: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-vercel-domain/api/webhook
   - 查看 Webhook 状态: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo

## 本地/联调（建议）

- 使用虚拟环境安装 requirements-dev.txt（含 Flask 等）
- 在 scripts/app.py 中用 Flask 模拟 /api/webhook（不入库，不提交）
- 通过 .env 或环境变量提供 TELEGRAM_BOT_TOKEN、DATABASE_URL 等

## 常见问题

- DB 无法连接：确认 DATABASE_URL 正确、网络可达、已启用 SSL（sslmode=require）
- 查询未命中：确认表名/列名与数据一致（仅支持字母/数字/下划线命名）
- 输出过多：本项目默认最小披露，不回显内部错误与实现

## 许可证

MIT