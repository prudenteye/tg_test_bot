# Telegram Bot 字符串逆序项目

这是一个简单的Telegram Bot项目，实现字符串逆序功能。支持Python和Node.js两种实现方式，可部署到Vercel、Heroku等平台。

## 功能特性

- 接收用户发送的字符串（不超过32字节）
- 返回字符串的逆序结果
- 支持Webhook方式接收消息
- 轻量级设计，适合无服务器部署

## 项目结构

```
├── python/                 # Python实现
│   ├── api/
│   │   └── webhook.py      # Vercel API端点
│   ├── requirements.txt    # Python依赖
│   └── vercel.json        # Vercel配置
├── nodejs/                 # Node.js实现
│   ├── api/
│   │   └── webhook.js      # Vercel API端点
│   ├── package.json       # Node.js依赖
│   └── vercel.json        # Vercel配置
├── heroku/                 # Heroku部署配置
│   ├── app.py             # Python Flask应用
│   ├── requirements.txt   # Python依赖
│   └── Procfile          # Heroku进程配置
└── docs/                  # 文档
    ├── setup-guide.md     # 详细设置指南
    └── deployment.md      # 部署指南

```

## 快速开始

### 1. 创建Telegram Bot

1. 在Telegram中找到 @BotFather
2. 发送 `/newbot` 命令
3. 按提示设置机器人名称和用户名
4. 获取API Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 选择部署方式

#### 方式一：Vercel部署（推荐）
- 支持Python和Node.js
- 免费额度充足
- 自动HTTPS
- 简单配置

#### 方式二：Heroku部署
- 支持多种语言
- 免费额度有限
- 需要信用卡验证

### 3. 环境变量配置

所有部署方式都需要设置以下环境变量：
- `TELEGRAM_BOT_TOKEN`: 从BotFather获取的API Token

## 部署指南

详细的部署步骤请参考：
- [设置指南](docs/setup-guide.md)
- [部署指南](docs/deployment.md)

## 本地测试

### Python版本
```bash
cd python
pip install -r requirements.txt
python -m flask run
```

### Node.js版本
```bash
cd nodejs
npm install
npm start
```

## 迁移到自有服务器

当您准备迁移到自有服务器时，请参考 [部署指南](docs/deployment.md) 中的"自有服务器部署"章节。

## 许可证

MIT License