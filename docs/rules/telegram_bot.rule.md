# Telegram Bot 项目标准化开发规范（Rule）

目标：以 Vercel Python Serverless + Supabase/Postgres 为后端，GitHub 托管，提供标准化目录、依赖、配置、调试与安全审计流程，便于快速复制新项目。

## 1. 语言与依赖规范
- Python 版本：建议 3.11（与 Vercel Python 运行时一致）。
- 依赖管理：
  - 部署依赖（Serverless 函数）：api/requirements.txt（仅保留线上必需，如 requests、psycopg[binary]）。
  - 本地开发依赖：requirements-dev.txt（如 flask、python-dotenv 等）。
  - 固定版本号，避免非确定性构建；定期升级且回归测试。
- 虚拟环境：本地开发务必使用 venv 或 uv，避免污染系统环境。

## 2. 资源与业务代码分离（强制）
- 原则：资源代码与业务代码完全分离、各自健壮和简洁。
  - 资源层（Resource）：仅包含与外部资源交互的代码（数据库、缓存、队列等）。例如 api/conn.py：连接池、健康检查、通用查询函数。不得包含业务决策或文案。
  - 业务层（Business）：接收/校验输入、编排流程、选择性调用资源层，并最小披露输出。例如 api/webhook.py：解析 Telegram 更新、长度限制、调用 conn.query_first()、统一简洁输出。
- I/O 最小化：Webhook GET 仅返回 {status, db_ok, commit.sha?}；不暴露内部配置、错误详情、外部端点。
- 可测试性：业务层应通过依赖注入或模块边界便于替换资源实现（如 mock 资源层）。

## 3. Vercel Webhook 与配置
- 目录：api/webhook.py 为后端入口（GET 状态最小化，POST 处理 Telegram 更新）；api/conn.py 为资源层。
- vercel.json（根目录）：
  - 指定函数运行时："functions": {"api/*.py": {"runtime": "python3.11"}}
  - 设定构建与路由：builds/routes
  - 配置 git.ignore：忽略 db/** 与 scripts/**
- index.html（根目录）：仅展示端点与数据库连通性（可选显示短提交 SHA）。
- 环境变量（Vercel 面板配置）：
  - TELEGRAM_BOT_TOKEN
  - DATABASE_URL（或 SUPABASE_DB_URL），建议强制 sslmode=require
  - 可选：SUPABASE_TABLE_NAME、SUPABASE_SEARCH_COLUMN

## 4. Git 规范与忽略策略
- 使用 GitHub 托管代码；main 受保护，采用 feature 分支 + Pull Request 合并。
- .gitignore 必须忽略：
  - 虚拟环境与缓存：.venv/ venv/ __pycache__/ *.pyc
  - 本地调试目录：scripts/ 与 db/
  - 私密文件：.env（保留 .env.example）
- .vercelignore 同步忽略 db/、scripts/（防止部署携带本地数据或调试脚本）。

## 5. 本地调试（虚拟环境与 Flask 仿真）
- 创建虚拟环境并安装 dev 依赖：
  - python3 -m venv .venv && source .venv/bin/activate
  - pip install -r requirements-dev.txt
- 创建 scripts/app.py（不入库）示例：
  """
  from flask import Flask, request, jsonify
  app = Flask(__name__)

  @app.get("/health")
  def health():
      return jsonify({"status": "ok"}), 200

  @app.post("/api/webhook")
  def webhook():
      data = request.get_json(silent=True) or {}
      return jsonify({"status": "ok", "echo": data}), 200

  if __name__ == "__main__":
      app.run(host="0.0.0.0", port=8787)
  """
- 调试前加载 .env（或使用 python-dotenv），确保能连接到测试数据库与开发 Bot。

## 6. 后端（Supabase/Postgres）部署与配置提醒
- 数据库连接串：DATABASE_URL（Postgres）附加 sslmode=require。
- 表与列命名：仅字母/数字/下划线，避免注入；在代码中对标识符做白名单检查。
- 权限与安全：最小权限；必要时配置网络白名单；敏感操作置于服务端。
- 性能：连接池（psycopg_pool）、connect_timeout、LIMIT。

## 7. README 内容模板（必写）
- 需求分析、架构设计、功能介绍
- 资源配置（环境变量、Webhook 配置）
- 接口规范（输入/输出与错误约定）：Webhook POST 输入关键字段；GET 健康检查最小输出
- 运维与监控
- TODO 与里程碑
- 版本信息（/api/webhook 返回 commit.sha）

## 8. 安全与代码审计清单（强制）
- 输入清洗：长度限制、类型检查、正则白名单或转义
- 传输安全：HTTPS；敏感配置与数据不入日志
- 错误处理：统一错误格式，避免泄露内部细节；超时与重试
- 隐私保护：避免上传/返回个人信息与技术栈详情；必要脱敏
- 依赖与密钥：锁版本；密钥走环境变量
- 文件完整性：记录哈希（sha256）并在 CI 校验；异常阻断发布
  - 示例：`git ls-files -z | xargs -0 shasum -a 256 > checksums.txt`
- 篡改提醒：状态页展示短提交 SHA，异常时提醒核查/回滚

## 9. 最小目录结构（示例）
.
├── api/
│   ├── webhook.py           # 业务层（最小 I/O）
│   ├── conn.py              # 资源层（连接/查询）
│   └── requirements.txt     # 线上依赖
├── index.html               # 状态页（仅端点/DB/短 SHA）
├── vercel.json              # 运行时/路由/忽略配置
├── requirements-dev.txt     # 本地调试依赖
├── .env.example             # 环境变量示例
├── .gitignore               # 忽略 scripts/ 与 db/
└── docs/
    └── rules/
        └── telegram_bot.rule.md

## 10. 验收清单
- [ ] /api/webhook GET 仅返回 {status, db_ok, commit.sha?}
- [ ] index.html 仅展示端点/DB/短 SHA
- [ ] 资源与业务分离：conn.py + webhook.py 边界清晰
- [ ] vercel.json 配置正确
- [ ] README 完整更新，接口输入/输出清晰
- [ ] 安全审计项逐条确认并记录