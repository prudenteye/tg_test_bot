# Telegram Webhook 机器人（Supabase/Postgres only，Vercel Python Functions）

本项目移除所有本地 CSV 读取逻辑，仅通过 Supabase/Postgres 查询返回结果；提供
- POST /api/webhook：Telegram Webhook 入口（仅处理文本消息，≤50 字节）
- GET /api/conn：健康检查（返回 db_ok 等）
- /index.html：入口页，展示 Webhook 与数据连接状态

## 部署要求

- Vercel（Python Runtime）
- 根目录 requirements.txt 安装依赖
- 在 Vercel Project Settings > Environment Variables 配置：
  - TELEGRAM_BOT_TOKEN
  - DATABASE_URL（建议带 sslmode=require）
  - SUPABASE_TABLE_NAME（如 accounts）
  - SUPABASE_SEARCH_COLUMN（如 account）

可选变量：
- BOT_TOKEN（若未设置 TELEGRAM_BOT_TOKEN，则使用该值）

## 环境变量示例

见 .env.example（仅示例，勿提交真实密钥）。

关键项：
- DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
- SUPABASE_TABLE_NAME=accounts
- SUPABASE_SEARCH_COLUMN=account

## 端点说明

- GET /api/conn
  - 响应：{"status":"ok","db_ok":true|false,"commit":{"sha":"xxxxxxx"}?}
  - 仅用于健康检查，不泄露内部实现

- POST /api/webhook
  - 输入：Telegram update JSON，仅处理 message.text，超过 50 字节将提示过长
  - 行为：到 Postgres 进行 ILIKE %text% 模糊搜索（使用 SUPABASE_TABLE_NAME/SUPABASE_SEARCH_COLUMN）
  - 输出：HTTP 始终返回 {"status":"ok"}（业务结果通过 Telegram sendMessage 返回给用户）
  - GET 方法返回 405

## 架构与代码位置

- 资源层（数据库等）：api/conn.py
  - 连接池（psycopg_pool 可选，缺失时回退直连）
  - ping_db()、health_status()、query_first()
  - class handler(BaseHTTPRequestHandler)：GET /api/conn
  - vercel_handler(request)：函数式入口（返回字符串 JSON）

- 业务层（Webhook）：api/webhook.py
  - 仅 POST，校验 ≤50 字节文本
  - 通过 api.conn.query_first 查询，组合最小消息内容并调用 Telegram sendMessage
  - class handler(BaseHTTPRequestHandler)：POST /api/webhook；GET 返回 405
  - vercel_handler(request)：函数式入口（返回字符串 JSON）
  - 注意：禁止覆盖类名 handler；不要写 handler = handler_vercel

## 本地开发（可选）

提供 scripts/ 本地模拟（已在仓库中）：
- 使用 Flask 模拟 / 和 /api/*，加载 .env
- 也可编写脚本直连 DATABASE_URL 做连通性检查

推荐步骤：
- 创建虚拟环境并安装依赖：pip install -r requirements.txt
- 设置 .env（参考 .env.example）
- 启动本地模拟服务或直接部署到 Vercel 进行验证

## 前端入口 index.html

- 自动请求 GET /api/conn 获取 db_ok
- 发送最小 POST 到 /api/webhook 检测可达性（HTTP 状态码 < 500 视为可达）
- 页面仅显示两项布尔状态，不输出敏感信息

## 安全与规范

- 统一错误信息，不泄露内部堆栈
- 输入长度限制与类型校验
- 数据库连接使用 sslmode=require
- 环境变量在 Vercel 配置，仓库不存放真实密钥
- 不再包含任何 CSV 或 pandas 依赖

## 常见问题

- 访问 /api/conn.py 报错：应访问 /api/conn（不要带 .py）
- 部署失败/构建被忽略：
  - vercel.json 保持最小化（仅 {"version": 2}）；不要配置 ignoreCommand（否则出现 “Ignored Build Step” 导致不触发构建）
  - 仅使用根目录 requirements.txt 安装依赖；不要创建 api/requirements.txt（避免与根依赖冲突）
- Vercel 报 issubclass 错误：不要用函数覆盖模块内 class handler 符号

## 变更摘要

- 移除 CSV 相关代码与依赖，改为 Supabase/Postgres 直连
- 新增/完善 GET /api/conn 健康检查
- Webhook 仅支持 POST；入口页 index.html 展示端点状态