"""
Database connection utilities (resource layer).
- Provides connection pool, health check (GET /api/conn), and simple query helpers.
- Keep business logic out of this module.
"""
import os
import json
from http.server import BaseHTTPRequestHandler
from typing import Optional, Dict, Any

# Optional Postgres driver (psycopg3)
try:
    import psycopg  # type: ignore
    from psycopg_pool import ConnectionPool  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
    _has_pg = True
except Exception:
    psycopg = None  # type: ignore
    ConnectionPool = None  # type: ignore
    dict_row = None  # type: ignore
    _has_pg = False

# Config
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE_NAME", "")
SUPABASE_SEARCH_COLUMN = os.environ.get("SUPABASE_SEARCH_COLUMN", "")

# Global pool cache
_pool = None  # type: ignore


def _is_safe_ident(name: str) -> bool:
    if not isinstance(name, str) or not name:
        return False
    return all(ch.isalnum() or ch == "_" for ch in name)


def _ensure_db_url_ssl(url: str) -> str:
    if not url:
        return url
    if "sslmode=" in url:
        return url
    return url + ("&sslmode=require" if "?" in url else "?sslmode=require")


def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if not _has_pg or not DATABASE_URL:
        return None
    dsn = _ensure_db_url_ssl(DATABASE_URL)
    try:
        _pool = ConnectionPool(dsn, min_size=0, max_size=5, kwargs={"connect_timeout": 2})
        return _pool
    except Exception:
        return None


def short_commit_sha() -> str:
    return (os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("GIT_COMMIT_SHA") or "")[:7]


def ping_db() -> bool:
    pool = get_pool()
    if not pool:
        return False
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
            return True
    except Exception:
        return False


def health_status() -> Dict[str, Any]:
    """
    Minimal health status for GET /api/conn.
    Returns:
      {
        "status": "ok",
        "db_ok": true|false,
        "commit": {"sha": "xxxxxxx"}?   # present only when available
      }
    """
    sha = short_commit_sha()
    payload: Dict[str, Any] = {
        "status": "ok",
        "db_ok": bool(ping_db()),
    }
    if sha:
        payload["commit"] = {"sha": sha}
    return payload


def query_first(q: str) -> Optional[Dict[str, Any]]:
    """
    Query first matched row by ILIKE on configured column.
    Returns a dict row or None. Avoids exposing table/column outside.
    """
    pool = get_pool()
    if not pool:
        return None
    table = SUPABASE_TABLE if _is_safe_ident(SUPABASE_TABLE) else "accounts"
    col = SUPABASE_SEARCH_COLUMN if _is_safe_ident(SUPABASE_SEARCH_COLUMN) else "account"
    sql = f'SELECT remarks, account_byte_length, account, account_hash FROM "{table}" WHERE "{col}" ILIKE %s LIMIT 1'
    try:
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (f"%{q}%",))
            return cur.fetchone()
    except Exception:
        return None


# HTTP handler to expose GET /api/conn as health endpoint
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body = json.dumps(health_status(), ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        except Exception:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"internal_error"}')