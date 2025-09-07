# Telegram Bot 项目标准化开发规范（Rule）

目标：以 Vercel Python Serverless + Supabase/Postgres 为后端，GitHub 托管，提供标准化目录、依赖、配置、调试与安全审计流程，便于快速复制新项目。

## 1. 语言与依赖规范
- Python 版本：建议 3.11（与 Vercel Python 运行时一致）。
- 依赖管理：
  - 部署依赖（Serverless 函数）：api/requirements.txt（仅保留线上必需，如 requests、psycopg[binary]）。
  - 本地开发依赖：requirements-dev.txt（如 flask、python-dotenv 等）。
  - 固定版本号，避免非确定性构建；定期升级且回归测试。
- 虚拟环境：本地开发务必使用 venv 或 uv，避免污染系统环境。

## 2. Vercel Webhook 与配置
- 目录：api/webhook.py 为唯一后端入口（GET 状态检查，POST 处理 Telegram 更新）。
- vercel.json（根目录）：
  - 指定函数运行时："functions": {"api/*.py": {"runtime": "python3.11"}}
  - 设定构建与路由：builds/routes
  - 配置 git.ignore：忽略 db/** 与 scripts/**
- index.html（根目录）：展示端点健康状态与代码版本信息（从 /api/webhook GET 的 JSON 中读取 commit 信息与运行环境）。
- 环境变量（在 Vercel 控制台配置）：
  - TELEGRAM_BOT_TOKEN
  - DATABASE_URL（或 SUPABASE_DB_URL），建议强制 sslmode=require
  - 可选：SUPABASE_TABLE_NAME、SUPABASE_SEARCH_COLUMN

## 3. Git 规范与忽略策略
- 使用 GitHub 托管代码；main 保护，采用 feature 分支 + Pull Request 合并。
- .gitignore 必须忽略：
  - 本地虚拟环境与缓存：.venv/ venv/ __pycache__/ *.pyc
  - 本地调试目录：scripts/ 与 db/
  - 私密文件：.env（保留 .env.example）
- .vercelignore 同步忽略 db/、scripts/（防止部署携带本地数据或调试脚本）。

## 4. 本地调试（虚拟环境与 Flask 仿真）
- 创建虚拟环境并安装 dev 依赖：
  - python3 -m venv .venv && source .venv/bin/activate
  - pip install -r requirements-dev.txt
- 创建 scripts/app.py（不入库，供本地调试）示例：
  """
  from flask import Flask, request, jsonify
  import requests, os

  app = Flask(__name__)

  @app.get("/health")
  def health():
      return jsonify({"status": "ok"}), 200

  @app.post("/api/webhook")
  def webhook():
      # 模拟 Telegram 更新透传到 Vercel（或本地处理）
      data = request.get_json(silent=True) or {}
      # TODO: 在此处调用与生产一致的 process_query() 逻辑（建议抽取可复用模块）
      return jsonify({"status": "ok", "echo": data}), 200

  if __name__ == "__main__":
      app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8787)))
  """
- 调试前加载 .env（或使用 python-dotenv），确保本地能连接到测试数据库与 Telegram 开发 Bot（谨慎发送真实消息）。

## 5. 后端（Supabase/Postgres）部署与配置提醒
- 数据库连接串：DATABASE_URL（Postgres）附加 sslmode=require。
- 表与列命名：仅字母/数字/下划线，避免注入；在代码中做标识符白名单检查。
- 权限与安全：
  - Supabase 数据库网络访问与 IP 允许列表（如需）。
  - 若使用 Supabase API/RLS，确保策略最小权限；敏感操作务必服务端执行。
- 性能：使用连接池（psycopg_pool），超时控制（connect_timeout）、LIMIT 限制。

## 6. README 内容模板（落库的必写文档）
- 需求分析：目标、用户场景、范围界定。
- 架构设计：目录结构、数据流、依赖、部署拓扑。
- 功能介绍：端点说明、处理逻辑、边界约束。
- 资源配置：环境变量、外部服务（Supabase、Telegram Webhook）配置方法。
- 接口规范：输入/输出 JSON 格式、字段说明、错误码约定。
- 运维与监控：健康检查、告警点、日志建议。
- TODO 与里程碑：当前进展、下一步工作清单。
- 版本信息：展示当前 GIT 提交（从 /api/webhook GET 返回的 commit 字段获得）。

## 7. 安全与代码审计清单（强制执行）
- 输入清洗：对外部输入进行长度限制、类型检查、正则白名单或转义处理。
- 传输安全：生产环境只使用 HTTPS；敏感配置与数据不在日志中输出。
- 错误处理：统一错误响应格式，避免泄露栈信息与内部实现细节；设计健壮的超时与重试机制。
- 隐私保护：避免上传/返回个人信息与项目的技术栈详情；必要时做脱敏。
- 依赖与密钥：锁定依赖版本并定期审计；所有密钥经环境变量注入，禁止入库。
- 文件完整性：定期记录项目文件的哈希（sha256）并校验；若检测到差异，触发告警。
  - 示例：`git ls-files -z | xargs -0 shasum -a 256 > checksums.txt`
  - CI 可对比 checksums.txt 与当前计算结果，异常即阻断发布。
- 篡改提醒：在状态页或监控系统中显示当前提交 SHA，异常时提醒人工核查与回滚。

## 8. 最小可用目录结构（示例）
.
├── api/
│   ├── webhook.py           # 仅后端入口（GET 状态/POST Webhook）
│   └── requirements.txt     # 线上依赖
├── index.html               # 状态页面（展示端点连通性与提交版本）
├── vercel.json              # 运行时/路由/忽略配置
├── requirements-dev.txt     # 本地调试依赖
├── .env.example             # 环境变量示例（不含真实密钥）
├── .gitignore               # 忽略 scripts/ 与 db/
└── docs/
    └── rules/
        └── telegram_bot.rule.md  # 本规范文件（可复制到新项目）

## 9. 验收清单（在每次提交前自检）
- [ ] /api/webhook GET 返回 Bot/Webhook/DB 状态与 commit 元信息
- [ ] index.html 能渲染端点状态与版本信息
- [ ] vercel.json 配置正确，部署成功
- [ ] .gitignore/.vercelignore 均忽略 scripts/ 与 db/
- [ ] README 完整更新，接口输入输出清晰
- [ ] 安全审计项逐条确认并记录