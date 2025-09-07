# Vercel Python Serverless function - standalone handler
# This file is the only entry point needed for deployment.
import json
import os
import requests
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, Union

# Support both env variable names
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

def _handle(request) -> Dict[str, Any]:
    # Method guard
    if hasattr(request, "method") and request.method != "POST":
        return {"statusCode": 405, "body": json.dumps({"error": "Method not allowed"})}

    if not BOT_TOKEN:
        return {"statusCode": 500, "body": json.dumps({"error": "BOT_TOKEN not configured"})}

    try:
        # Extract JSON body (compatible with Flask-like or Vercel request)
        data = None
        if hasattr(request, "get_json") and callable(getattr(request, "get_json")):
            data = request.get_json()
        elif hasattr(request, "json") and request.json:
            data = request.json
        elif hasattr(request, "body"):
            body = request.body
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            data = json.loads(body) if body else {}
        else:
            raw = getattr(request, "data", {})
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = raw

        if not data:
            return {"statusCode": 400, "body": json.dumps({"error": "No data received"})}

        # Ignore non-message updates
        if "message" not in data:
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

        message = data["message"]
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        # Only process text
        text = message.get("text")
        if text is None:
            send_message(chat_id, "请发送文本消息！")
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

        # 32-byte limit (UTF-8)
        if len(text.encode("utf-8")) > 32:
            send_message(chat_id, "消息太长了！请发送不超过32字节的字符串。")
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

        # Reverse and reply
        reversed_text = text[::-1]
        send_message(chat_id, f"逆序结果：{reversed_text}")

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}

def send_message(chat_id: Union[int, str], text: str) -> Dict[str, Any]:
    if not TELEGRAM_API_URL or not chat_id:
        return {"ok": False, "error": "Bot token or chat_id missing"}

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return {"ok": False, "error": str(e)}

# Expose a class-based handler for Vercel runtime scanning
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check
        body = json.dumps({"status": "ok", "bot_configured": bool(BOT_TOKEN)})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b""
            class Req:
                method = "POST"
                def __init__(self, body: bytes):
                    self.body = body
            result = _handle(Req(raw))
            status = result.get("statusCode", 200)
            body = result.get("body", "{}")
            if isinstance(body, (dict, list)):
                body = json.dumps(body)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        except Exception:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Internal server error"}')

# Vercel entry point
def handler_vercel(request):
    return _handle(request)