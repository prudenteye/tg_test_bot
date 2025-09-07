# Vercel Python Serverless function - webhook handler (business layer, minimal I/O)
import json
import os
import requests
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, Union

from api import conn  # resource layer

# Telegram
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def _parse_body(request) -> Dict[str, Any]:
    try:
        if hasattr(request, "get_json") and callable(getattr(request, "get_json")):
            return request.get_json() or {}
        if hasattr(request, "json") and request.json:
            return request.json or {}
        if hasattr(request, "body"):
            body = request.body
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
        raw = getattr(request, "data", {})
        if isinstance(raw, str):
            return json.loads(raw)
        return raw or {}
    except Exception:
        return {}





def _handle(request) -> Dict[str, Any]:
    # Only POST for webhook processing
    if hasattr(request, "method") and request.method != "POST":
        return {"statusCode": 405, "body": json.dumps({"error": "method_not_allowed"})}

    if not BOT_TOKEN:
        return {"statusCode": 500, "body": json.dumps({"error": "server_not_configured"})}

    data = _parse_body(request)
    if not data:
        return {"statusCode": 400, "body": json.dumps({"error": "bad_request"})}

    # Ignore non-message updates
    message = data.get("message")
    if not isinstance(message, dict):
        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text")

    # Only process text
    if not isinstance(text, str):
        if chat_id:
            send_message(chat_id, "请发送文本消息。")
        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    # 50-byte limit (UTF-8)
    if len(text.encode("utf-8")) > 50:
        if chat_id:
            send_message(chat_id, "消息过长（≤50字节）。")
        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    # DB query (resource layer)
    try:
        row = conn.query_first(text.strip())
        if row:
            msg = None
            if (row.get("remarks") is not None) and str(row.get("remarks")) != "":
                msg = str(row.get("remarks"))
            elif row.get("account_byte_length") is not None:
                msg = str(row.get("account_byte_length"))
            else:
                msg = "已找到匹配记录。"
            if chat_id:
                send_message(chat_id, msg)
        else:
            if chat_id:
                send_message(chat_id, "未找到记录。")
    except Exception:
        if chat_id:
            send_message(chat_id, "查询失败，请稍后再试。")

    return {"statusCode": 200, "body": json.dumps({"status": "ok"})}


def send_message(chat_id: Union[int, str], text: str) -> Dict[str, Any]:
    if not TELEGRAM_API_URL or not chat_id:
        return {"ok": False}
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        return {"ok": False}


# Class-based handler for Vercel runtime
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # webhook no longer serves GET; health is provided by GET /api/conn
        self.send_response(405)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"method_not_allowed"}')

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
            self.wfile.write(b'{"error":"internal_error"}')


# Vercel entry point
def handler_vercel(request):
    # Return string body for maximal runtime compatibility
    result = _handle(request)
    body = result.get("body", "{}")
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    return body

# Export default handler for Vercel runtime compatibility
handler = handler_vercel
# Export default handler for Vercel runtime compatibility
handler = handler_vercel