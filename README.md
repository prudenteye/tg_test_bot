# Telegram Bot CSV 查询（Vercel Python Serverless）

本项目是基于 Vercel Python Serverless 的 Telegram Bot。机器人接收用户文本，将其作为关键字在 CSV 指定列中进行包含匹配（模糊匹配）并返回结果。
- 输入长度限制：不超过 50 字节（UTF-8）
- 匹配列：默认 account（可通过环境变量 CSV_KEY_COLUMN 覆盖）
- 返回优先级：remarks → account_byte_length → 整行预览（含截断保护）

## 项目结构

```
.
├── api/
│   ├── webhook.py          # 主功能入口（/api/webhook）
│   └── requirements.txt    # 函数依赖（requests、pandas）
├── db/
│   └── wxid_test.csv       # 示例数据（部署后路径 /var/task/db/wxid_test.csv）
├── .env.example
├── .gitignore
├── .vercelignore
└── README.md
```

## 主功能入口与运行逻辑

- 入口文件：api/webhook.py
  - GET /api/webhook：健康检查，返回
    - bot_configured（是否配置了 Bot Token）
    - csv_configured（是否配置了 CSV_FILE_PATH）
    - pandas_available（是否可用 pandas）
  - POST /api/webhook：处理 Telegram Webhook 更新
    - 仅处理文本消息（超过 50 字节会提示过长）
    - 调用 process_query(text) 执行查询：
      - 首次使用 pandas 读取 CSV（encoding="utf-8-sig"），缓存于内存（Serverless 实例级）
      - 按 CSV_KEY_COLUMN（默认 account）进行包含匹配（模糊匹配），返回首条匹配记录
      - 返回优先级：remark → byte_length → 整行预览（含长度截断）

## 在 Vercel 上部署

1) 导入仓库
- 在 Vercel 中 New Project，选择本仓库创建项目
- Vercel 自动识别 api/ 为 Serverless Functions

2) 配置环境变量（Project Settings → Environment Variables）
- TELEGRAM_BOT_TOKEN（必填）：从 BotFather 获取的 Token
- CSV_FILE_PATH（建议设置）：CSV 绝对路径
  - 若将 CSV 放在仓库 db/ 目录并随代码部署，运行时路径通常为：/var/task/db/wxid_test.csv
  - 示例：CSV_FILE_PATH=/var/task/db/wxid_test.csv
- CSV_KEY_COLUMN（可选）：用于匹配的键列名，默认 account

3) 构建与依赖
- Vercel 会基于 api/requirements.txt 自动安装依赖（requests、pandas）
- 部署完成后访问 https://your-vercel-domain/api/webhook 验证健康检查

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

## CSV 准备与路径说明

- 推荐将 CSV 放在仓库 db/ 目录（例如 db/wxid_test.csv），随代码一并部署
  - 部署后可用路径：/var/task/db/wxid_test.csv
- 若 CSV 包含 remarks 列，将优先返回该列值；否则尝试返回 account_byte_length；都没有则返回整行预览
- 文件编码建议 UTF-8 或 UTF-8 with BOM（代码使用 encoding="utf-8-sig" 兼容）

## 使用方式（联调建议）

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
- CSV_FILE_PATH=/var/task/db/wxid_test.csv
- CSV_KEY_COLUMN=account

## 常见问题

- pandas 不可用：确认 api/requirements.txt 包含 pandas，重新部署
- CSV 无法加载：检查 CSV_FILE_PATH 是否为运行时可读的绝对路径，且文件已随代码打包
- 查询未命中：确认 CSV_KEY_COLUMN 存在并与消息文本字符串完全相等（精确匹配）
- 返回内容为空：若 CSV 无 remark 与 byte_length，会回退为整行预览

## 许可证

MIT