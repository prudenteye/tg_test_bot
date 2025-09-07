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

# Main feature config placeholders
CSV_FILE_PATH = os.environ.get("CSV_FILE_PATH") or "/var/task/db/wxid_test.csv"
CSV_KEY_COLUMN = os.environ.get("CSV_KEY_COLUMN", "account")

# Supabase/Postgres config
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
FEATURE_USE_SUPABASE = (os.environ.get("FEATURE_USE_SUPABASE", "false").lower() == "true")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE_NAME", "accounts")
SUPABASE_SEARCH_COLUMN = os.environ.get("SUPABASE_SEARCH_COLUMN", CSV_KEY_COLUMN)

# Supabase/Postgres (via psycopg3) config
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
FEATURE_USE_SUPABASE = (os.environ.get("FEATURE_USE_SUPABASE", "false").lower() == "true")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE_NAME", "accounts")
SUPABASE_SEARCH_COLUMN = os.environ.get("SUPABASE_SEARCH_COLUMN", CSV_KEY_COLUMN)

# Optional pandas import (for deployment, ensure pandas is installed)
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    pd = None
    HAS_PANDAS = False

# Optional Postgres driver (psycopg3) for Supabase
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

# Global DB pool (may persist across invocations)
_PG_POOL = None  # type: ignore

# Optional Postgres driver (psycopg3) for Supabase
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

# Global DB pool (may persist across invocations in serverless warm starts)
_PG_POOL = None  # type: ignore

# Simple in-memory cache; for serverless, may reload per invocation
_DF_CACHE = None  # type: ignore

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

        # 50-byte limit (UTF-8)
        if len(text.encode("utf-8")) > 50:
            send_message(chat_id, "消息太长了！请发送不超过50字节的字符串。")
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

        # CSV query
        result_msg = process_query(text)
        send_message(chat_id, result_msg)

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}

def _load_dataframe():
    global _DF_CACHE
    if _DF_CACHE is not None:
        return _DF_CACHE
    if not HAS_PANDAS:
        return None
    if not CSV_FILE_PATH:
        return None
    try:
        df = pd.read_csv(CSV_FILE_PATH, encoding="utf-8-sig")
        _DF_CACHE = df
        return df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None

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
    return (url + ("&sslmode=require" if "?" in url else "?sslmode=require"))

def _get_pool():
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    if not HAS_PG or not DATABASE_URL:
        return None
    dsn = _ensure_db_url_ssl(DATABASE_URL)
    try:
        # Small pool is enough for serverless
        _PG_POOL = ConnectionPool(dsn, min_size=0, max_size=5, kwargs={"connect_timeout": 5})
        return _PG_POOL
    except Exception as e:
        print(f"Error creating DB pool: {e}")
        return None

def _query_db(q: str):
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

def _is_safe_ident(name: str) -> bool:
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
        _PG_POOL = ConnectionPool(dsn, min_size=0, max_size=5, kwargs={"connect_timeout": 5})
        return _PG_POOL
    except Exception as e:
        print(f"Error creating DB pool: {e}")
        return None

def _query_db(q: str):
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

def process_query(query_text: str) -> str:
    # Basic placeholder: guide for deployment configuration and usage
    if not HAS_PANDAS:
        return "功能占位：未检测到 pandas。请在部署环境安装 pandas，并配置 CSV_FILE_PATH/CSV_KEY_COLUMN。"
    if not CSV_FILE_PATH:
        return "功能占位：未配置 CSV_FILE_PATH 环境变量。请设置 CSV 文件路径后重试。"
    df = _load_dataframe()
    if df is None:
        return "功能占位：无法加载 CSV 文件，请检查路径和文件格式。"
    key_col = CSV_KEY_COLUMN if CSV_KEY_COLUMN in df.columns else None
    if key_col is None:
        return f"功能占位：CSV 中不存在配置的键列 '{CSV_KEY_COLUMN}'，当前列为：{list(df.columns)}"
    try:
        # 模糊匹配（包含），对空白输入与非字符串数据做兼容
        q = (str(query_text) if query_text is not None else "").strip()
        if not q:
            return "请输入非空的查询关键字。"

        # Prefer Supabase DB if enabled and driver available
        if FEATURE_USE_SUPABASE and HAS_PG and DATABASE_URL:
            row_db = _query_db(q)
            if isinstance(row_db, dict) and row_db:
                if "remarks" in row_db and row_db.get("remarks") not in (None, ""):
                    return str(row_db["remarks"])
                if "account_byte_length" in row_db and row_db.get("account_byte_length") is not None:
                    return str(row_db["account_byte_length"])
                # Fallback preview (limit items)
                items = []
                max_items = 20
                for i, (k, v) in enumerate(row_db.items()):
                    if i >= max_items:
                        items.append("...后续字段已截断")
                        break
                    items.append(f"{k}: {v}")
                return "查询结果：\
" + "\
".join(items)
            # if no db result, fall back to CSV

        # CSV fallback
        series = df[key_col].astype(str)
        matched = df[series.str.contains(q, regex=False, na=False)]
        if matched.empty:
            return f"未找到记录：{query_text}"
        # 优先返回 remarks 或 account_byte_length
        if "remarks" in matched.columns:
            val = matched.iloc[0]["remarks"]
            return str(val) if val is not None else "未找到 remarks 内容"
        if "account_byte_length" in matched.columns:
            return str(matched.iloc[0]["account_byte_length"])
        # 简要返回第一条记录的所有字段
        row = matched.iloc[0].to_dict()
        # 控制返回长度，避免过长消息
        preview_items = []
        max_len = 600
        curr = 0
        for k, v in row.items():
            item = f"{k}: {v}"
            if curr + len(item) + 1 > max_len:
                preview_items.append("...后续字段已截断")
                break
            preview_items.append(item)
            curr += len(item) + 1
        return "查询结果：\n" + "\n".join(preview_items)
    except Exception as e:
        print(f"Error processing query: {e}")
        return "查询失败：请检查 CSV 内容与配置。"

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
        body = json.dumps({
            "status": "ok",
            "bot_configured": bool(BOT_TOKEN),
            "csv_configured": bool(CSV_FILE_PATH),
            "pandas_available": HAS_PANDAS,
            "db_configured": bool(DATABASE_URL),
            "db_driver_available": HAS_PG
        })
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