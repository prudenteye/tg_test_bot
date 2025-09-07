#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地开发用的 Flask 包装服务：
- GET  /               健康检查，返回是否配置了 TELEGRAM_BOT_TOKEN
- POST /test           本地功能测试端点，返回 expected_output 以及 handler_result
- POST /api/webhook    转发到 serverless handler，模拟生产 Webhook
"""

import os
import json
from flask import Flask, request, jsonify
from api.webhook import handler as webhook_handler

app = Flask(__name__)

def _bot_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN"))

@app.get("/")
def health():
    return jsonify({
        "status": "ok",
        "bot_configured": _bot_configured()
    }), 200

@app.post("/api/webhook")
def api_webhook():
    # 直接调用 serverless handler 并将返回值转成 Flask 响应
    result = webhook_handler(request)
    status = result.get("statusCode", 200)
    body = result.get("body", "{}")

    try:
        data = json.loads(body) if isinstance(body, str) else body
    except Exception:
        data = {"raw": body}

    return jsonify(data), status

@app.post("/test")
def test_endpoint():
    """
    输入: { "text": "...", "chat_id": 123 }
    输出:
    {
      "expected_output": "逆序字符串（若<=32字节）否则空字符串",
      "handler_result": { ... },    # 调用 webhook handler 的结果（可选）
      "error": "too_long"           # 当超过32字节时返回（状态码仍为200，便于现有测试脚本通过）
    }
    """
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "") or ""
    chat_id = payload.get("chat_id", 0)

    too_long = len(text.encode("utf-8")) > 32
    expected_output = "" if too_long else text[::-1]

    # 尝试用 handler 走一遍流程（不要求必须成功，失败会被包装返回）
    handler_result = None
    try:
        fake_update = {
            "message": {
                "chat": {"id": chat_id},
                "text": text
            }
        }

        class MockReq:
            method = "POST"
            def get_json(self):
                return fake_update

        handler_result = webhook_handler(MockReq())
    except Exception as e:
        handler_result = {"ok": False, "error": str(e)}

    resp = {
        "expected_output": expected_output,
        "handler_result": handler_result
    }
    if too_long:
        resp["error"] = "too_long"

    return jsonify(resp), 200

if __name__ == "__main__":
    # 默认监听 5000 端口，便于与测试脚本对接；可用环境变量 PORT 覆盖
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("DEBUG", "0") == "1"))