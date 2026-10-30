"""
NyayPath Rate Limiting Engine
Serverless-compatible persistent rate limiting for authentication and verification endpoints.
Prevents brute-force attacks across distributed instances using Supabase/SQLite persistence.
"""

import os
import time
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        self.use_supabase = bool(url and key and create_client)
        self.supabase: Optional[Client] = None
        self._local_db_path = os.environ.get("CAMPUS_SQLITE_DB", "campus_cases_persistent.db")

        if self.use_supabase:
            try:
                self.supabase = create_client(url, key)
            except Exception as e:
                logger.warning(f"RateLimiter Supabase init warning: {e}")
                self.use_supabase = False
        else:
            self._init_sqlite()

    def _init_sqlite(self):
        try:
            conn = sqlite3.connect(self._local_db_path)
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_attempts (
                key TEXT PRIMARY KEY,
                attempt_count INTEGER NOT NULL DEFAULT 1,
                last_attempt INTEGER NOT NULL,
                blocked_until INTEGER NOT NULL DEFAULT 0
            );
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init rate limit sqlite: {e}")

    def check_rate_limit(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = 900,
        cooldown_seconds: int = 900
    ) -> Tuple[bool, int]:
        """
        Checks whether the action for `key` is rate-limited.
        Returns (is_allowed: bool, retry_after_seconds: int).
        """
        now = int(time.time())

        # 1. Supabase implementation
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("rate_limit_attempts").select("*").eq("key", key).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    blocked_until = row.get("blocked_until", 0)
                    if blocked_until > now:
                        return False, int(blocked_until - now)

                    last_attempt = row.get("last_attempt", 0)
                    count = row.get("attempt_count", 0)

                    if now - last_attempt > window_seconds:
                        # Reset window
                        self.supabase.table("rate_limit_attempts").update({
                            "attempt_count": 0,
                            "last_attempt": now,
                            "blocked_until": 0
                        }).eq("key", key).execute()
                        return True, 0

                    if count >= max_attempts:
                        blocked_until = now + cooldown_seconds
                        self.supabase.table("rate_limit_attempts").update({
                            "blocked_until": blocked_until
                        }).eq("key", key).execute()
                        return False, cooldown_seconds

                return True, 0
            except Exception as e:
                logger.warning(f"Rate limit Supabase query failed: {e}")

        # 2. SQLite implementation
        try:
            conn = sqlite3.connect(self._local_db_path)
            cur = conn.cursor()
            cur.execute("SELECT attempt_count, last_attempt, blocked_until FROM rate_limit_attempts WHERE key = ?", (key,))
            row = cur.fetchone()

            if row:
                count, last_attempt, blocked_until = row
                if blocked_until > now:
                    conn.close()
                    return False, int(blocked_until - now)

                if now - last_attempt > window_seconds:
                    cur.execute("UPDATE rate_limit_attempts SET attempt_count = 0, last_attempt = ?, blocked_until = 0 WHERE key = ?", (now, key))
                    conn.commit()
                    conn.close()
                    return True, 0

                if count >= max_attempts:
                    blocked_until = now + cooldown_seconds
                    cur.execute("UPDATE rate_limit_attempts SET blocked_until = ? WHERE key = ?", (blocked_until, key))
                    conn.commit()
                    conn.close()
                    return False, cooldown_seconds

            conn.close()
            return True, 0
        except Exception as e:
            logger.error(f"Rate limit SQLite error: {e}")
            return True, 0

    def record_failure(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = 900,
        cooldown_seconds: int = 900
    ):
        """Records a failed attempt for `key` and activates cooldown if limit reached."""
        now = int(time.time())

        # 1. Supabase
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("rate_limit_attempts").select("*").eq("key", key).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    count = row.get("attempt_count", 0) + 1
                    blocked_until = (now + cooldown_seconds) if count >= max_attempts else 0
                    self.supabase.table("rate_limit_attempts").update({
                        "attempt_count": count,
                        "last_attempt": now,
                        "blocked_until": blocked_until
                    }).eq("key", key).execute()
                else:
                    self.supabase.table("rate_limit_attempts").insert({
                        "key": key,
                        "attempt_count": 1,
                        "last_attempt": now,
                        "blocked_until": 0
                    }).execute()
                return
            except Exception as e:
                logger.warning(f"Rate limit record failure on Supabase failed: {e}")

        # 2. SQLite
        try:
            conn = sqlite3.connect(self._local_db_path)
            cur = conn.cursor()
            cur.execute("SELECT attempt_count FROM rate_limit_attempts WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                count = row[0] + 1
                blocked_until = (now + cooldown_seconds) if count >= max_attempts else 0
                cur.execute("UPDATE rate_limit_attempts SET attempt_count = ?, last_attempt = ?, blocked_until = ? WHERE key = ?", (count, now, blocked_until, key))
            else:
                cur.execute("INSERT INTO rate_limit_attempts (key, attempt_count, last_attempt, blocked_until) VALUES (?, 1, ?, 0)", (key, now))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Rate limit SQLite record failure error: {e}")

    def reset_limit(self, key: str):
        """Resets counter upon successful authentication."""
        if self.use_supabase and self.supabase:
            try:
                self.supabase.table("rate_limit_attempts").delete().eq("key", key).execute()
            except Exception:
                pass
        try:
            conn = sqlite3.connect(self._local_db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM rate_limit_attempts WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception:
            pass

rate_limiter = RateLimiter()

def get_client_ip(request: Request) -> str:
    """Extracts client IP considering standard proxies/load balancers (Vercel / Cloudflare)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

def enforce_rate_limit(
    request: Request,
    action: str,
    target_id: Optional[str] = None,
    max_attempts: int = 5,
    window_seconds: int = 900,
    cooldown_seconds: int = 900
):
    """Enforces rate limit or raises HTTP 429 Too Many Requests."""
    ip = get_client_ip(request)
    limit_key = f"{action}:{target_id or ''}:{ip}"
    allowed, retry_after = rate_limiter.check_rate_limit(
        limit_key,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        cooldown_seconds=cooldown_seconds
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Access temporarily locked. Please retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )
    return limit_key

def record_rate_limit_failure(
    request: Request,
    action: str,
    target_id: Optional[str] = None,
    max_attempts: int = 5,
    window_seconds: int = 900,
    cooldown_seconds: int = 900
):
    """Records a failure against the request's rate-limiting key."""
    ip = get_client_ip(request)
    limit_key = f"{action}:{target_id or ''}:{ip}"
    rate_limiter.record_failure(
        limit_key,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        cooldown_seconds=cooldown_seconds
    )

def reset_rate_limit(
    request: Request,
    action: str,
    target_id: Optional[str] = None
):
    """Resets the rate-limiting key upon successful authentication."""
    ip = get_client_ip(request)
    limit_key = f"{action}:{target_id or ''}:{ip}"
    rate_limiter.reset_limit(limit_key)

