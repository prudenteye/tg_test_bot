# Vercel Python Serverless function - standalone handler (Supabase/Postgres only)
import json
import os
import requests
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, Union, Optional

# Telegram
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

# Supabase/Postgres config (via direct Postgres connection)
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE_NAME", "accounts")
SUPABASE_SEARCH_COLUMN = os.environ.get("SUPABASE_SEARCH_COLUMN", "account")

# Optional Postgres driver (psycopg3)
try:
    import psycopg  # type: ignore
    from psycopg_pool import ConnectionPool  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
    HAS_PG = True
except Exception:
    psycopg = None
    ConnectionPool = None
    dict_row = None
    HAS_PG = False

# Global caches (may persist across warm invocations)
_PG_POOL = None  # type: ignore


def _handle(request) -> Dict[str, Any]:
    # Only POST for webhook processing
    if hasattr(request, "method") and request.method != "POST":
        return {"statusCode": 405, "body": json.dumps({"error": "Method not allowed"})}

    if not BOT_TOKEN:
        return {"statusCode": 500, "body": json.dumps({"error": "BOT_TOKEN not configured"})}

    try:
        # Extract JSON body (compatible with Vercel/flask-like)
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

        # 50-byte limit (UTF-8)
        if len(text.encode("utf-8")) > 50:
            send_message(chat_id, "消息太长了！请发送不超过50字节的字符串。")
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

        # Query (Supabase/Postgres only)
        result_msg = process_query(text)
        send_message(chat_id, result_msg)

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


# ---------------- Helpers: DB (Supabase/Postgres) ----------------

def _is_safe_ident(name: str) -> bool:
    # allow letters, numbers, underscore only
    if not isinstance(name, str) or not name:
        return False
    for ch in name:
        if not (ch.isalnum() or ch == "_"):
            return False
    return True


def _ensure_db_url_ssl(url: str) -> str:
    if not url:
        return url
    if "sslmode=" in url:
        return url
    return url + ("&sslmode=require" if "?" in url else "?sslmode=require")


def _get_pool():
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    if not HAS_PG or not DATABASE_URL:
        return None
    dsn = _ensure_db_url_ssl(DATABASE_URL)
    try:
        # reduce connect timeout to speed up Preview even if DB unavailable
        _PG_POOL = ConnectionPool(dsn, min_size=0, max_size=5, kwargs={"connect_timeout": 2})
        return _PG_POOL
    except Exception as e:
        print(f"Error creating DB pool: {e}")
        return None


def _query_db(q: str) -> Optional[Dict[str, Any]]:
    pool = _get_pool()
    if not pool:
        return None
    table = SUPABASE_TABLE if _is_safe_ident(SUPABASE_TABLE) else "accounts"
    col = SUPABASE_SEARCH_COLUMN if _is_safe_ident(SUPABASE_SEARCH_COLUMN) else "account"
    sql = f'SELECT remarks, account_byte_length, account, account_hash FROM "{table}" WHERE "{col}" ILIKE %s LIMIT 1'
    try:
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (f"%{q}%",))
            row = cur.fetchone()
            return row  # dict or None
    except Exception as e:
        print(f"DB query error: {e}")
        return None


# ---------------- Query orchestrator ----------------

def process_query(query_text: str) -> str:
    try:
        q = (str(query_text) if query_text is not None else "").strip()
        if not q:
            return "请输入非空的查询关键字。"

        if HAS_PG and DATABASE_URL:
            row_db = _query_db(q)
            if isinstance(row_db, dict) and row_db:
                if "remarks" in row_db and row_db.get("remarks") not in (None, ""):
                    return f"{row_db['remarks']} [supabase]"
                if "account_byte_length" in row_db and row_db.get("account_byte_length") is not None:
                    return f"{row_db['account_byte_length']} [supabase]"
                # Fallback preview
                items = []
                max_items = 20
                for i, (k, v) in enumerate(row_db.items()):
                    if i >= max_items:
                        items.append("...后续字段已截断")
                        break
                    items.append(f"{k}: {v}")
                return "查询结果：\n" + "\n".join(items) + " [supabase]"

        # Not found or DB not configured
        if not (HAS_PG and DATABASE_URL):
            return "服务未配置数据库，请联系管理员。"
        return f"未找到记录：{query_text}"
    except Exception as e:
        print(f"Error processing query: {e}")
        return "查询失败：请检查数据库配置。"


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


# Expose a class-based handler for Vercel runtime scanning with status page
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Build status values
        bot_cfg = bool(BOT_TOKEN)
        db_cfg = bool(DATABASE_URL)

        # DB connectivity check (fast-fail)
        db_ok = False
        db_error = ""
        try:
            pool = _get_pool()
            if db_cfg and HAS_PG and pool:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                        db_ok = True
        except Exception as e:
            db_ok = False
            db_error = str(e)

        # Telegram webhook info
        webhook_ok = False
        webhook_url = ""
        webhook_err = ""
        try:
            if bot_cfg and TELEGRAM_API_URL:
                info_url = f"{TELEGRAM_API_URL}/getWebhookInfo"
                r = requests.get(info_url, timeout=8)
                if r.ok:
                    ji = r.json()
                    webhook_ok = bool(ji.get("ok"))
                    result = ji.get("result") or {}
                    webhook_url = result.get("url") or ""
                    last_err = result.get("last_error_message") or ""
                    if last_err:
                        webhook_err = last_err
        except Exception as e:
            webhook_ok = False
            webhook_err = str(e)

        # Commit metadata (Vercel CI/CD)
        commit_sha = (os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("GIT_COMMIT_SHA") or "")[:7]
        status_json = {
            "status": "ok",
            "bot_configured": bot_cfg,
            "webhook_ok": webhook_ok,
            "webhook_url": webhook_url,
            "webhook_error": webhook_err,
            "db_configured": db_cfg,
            "db_driver_available": HAS_PG,
            "db_ok": db_ok,
            "db_error": db_error,
            "commit": {
                "sha": commit_sha,
                "message": os.environ.get("VERCEL_GIT_COMMIT_MESSAGE") or "",
                "branch": os.environ.get("VERCEL_GIT_COMMIT_REF") or "",
                "repo_owner": os.environ.get("VERCEL_GIT_REPO_OWNER") or "",
                "repo_slug": os.environ.get("VERCEL_GIT_REPO_SLUG") or "",
                "env": os.environ.get("VERCEL_ENV") or ""
            }
        }

        accept = (self.headers.get("Accept") or "").lower()
        if "text/html" in accept or "*/*" in accept:
            html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Service Status</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:16px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;color:#fff;font-size:12px;margin-left:6px}}
.ok{{background:#2e7d32}} .warn{{background:#ed6c02}} .err{{background:#c62828}}
code,pre{{background:#f6f8fa;padding:8px;border-radius:6px}}
</style>
</head><body>
<h1>服务状态{(' · ' + commit_sha) if (locals().get('commit_sha')) else ''}</h1>
<ul>
  <li>Telegram Bot 配置：{str(bot_cfg)} <span class="badge {'ok' if bot_cfg else 'err'}">{'OK' if bot_cfg else 'MISSING'}</span></li>
  <li>Webhook：{str(webhook_ok)} <span class="badge {'ok' if webhook_ok else 'warn'}">{'OK' if webhook_ok else 'CHECK'}</span>
    {(' 当前 URL: ' + webhook_url) if webhook_url else ''}{('；错误：' + webhook_err) if webhook_err else ''}</li>
  <li>Supabase(DB) 配置：{str(db_cfg)}，驱动：{str(HAS_PG)}，连接：{str(db_ok)}
    <span class="badge {'ok' if db_ok else ('warn' if db_cfg else 'err')}">{'OK' if db_ok else ('CFG' if db_cfg else 'MISSING')}</span>
    {(' 错误：' + db_error) if (db_cfg and not db_ok and db_error) else ''}</li>
</ul>
<h3>原始数据</h3>
<pre>{json.dumps(status_json, ensure_ascii=False, indent=2)}</pre>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            body = json.dumps(status_json, ensure_ascii=False)
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