"""Database & Authentication Manager for Linework AI
Handles SQLite persistence for users, session tokens, trial sheet usage,
pro subscriptions, and bKash payment verification requests.
"""
import os
import sys
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

if getattr(sys, "frozen", False):
    DB_DIR = Path(sys.executable).resolve().parent / "data"
else:
    DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "linework_app.db"
UPLOAD_DIR = DB_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            plan TEXT DEFAULT 'free',
            free_sheets_used INTEGER DEFAULT 0,
            pro_expires_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            phone TEXT NOT NULL,
            amount INTEGER DEFAULT 300,
            trx_id TEXT NOT NULL,
            screenshot_path TEXT,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        # Ensure default admin exists
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cur.fetchone():
            salt = secrets.token_hex(16)
            pwd_hash = _hash_password("admin123", salt)
            cur.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, status, plan, pro_expires_at)
            VALUES (?, ?, ?, ?, 'admin', 'active', 'pro', ?)
            """, ("admin", "admin@linework.ai", pwd_hash, salt, "2099-12-31 23:59:59"))
            conn.commit()


def get_default_admin():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        u = cur.fetchone()
        if u:
            return dict(u)
        return dict(id=1, username="admin", email="admin@linework.ai", role="admin", status="active", plan="pro", free_sheets_used=0)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()


def create_user(username, password, email=None, role="user"):
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt)
    with get_db() as conn:
        try:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, status, plan, free_sheets_used)
            VALUES (?, ?, ?, ?, ?, 'active', 'free', 0)
            """, (username, email, pwd_hash, salt, role))
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def verify_user(username, password):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
        user = cur.fetchone()
        if not user:
            return None
        pwd_hash = _hash_password(password, user["salt"])
        if pwd_hash == user["password_hash"]:
            return dict(user)
        return None


def create_session(user_id):
    token = secrets.token_hex(32)
    with get_db() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        conn.commit()
    return token


def get_user_from_token(token):
    if not token:
        return None
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.token = ?
        """, (token,))
        user = cur.fetchone()
        if not user:
            return None
        d = dict(user)
        # Check pro expiration
        if d["plan"] == "pro" and d["pro_expires_at"]:
            try:
                exp = datetime.fromisoformat(d["pro_expires_at"])
                if datetime.now() > exp and d["role"] != "admin":
                    d["plan"] = "free"
                    conn.execute("UPDATE users SET plan = 'free' WHERE id = ?", (d["id"],))
                    conn.commit()
            except Exception:
                pass
        return d


def delete_session(token):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def can_user_process_sheet(user_id):
    """Check if user has Pro or has remaining free trial sheets."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        if not u:
            return False, "User not found"
        if u["status"] != "active":
            return False, "Account is pending admin approval or suspended."
        if u["role"] == "admin" or u["plan"] == "pro":
            return True, "PRO"
        if u["free_sheets_used"] < 2:
            left = 2 - u["free_sheets_used"]
            return True, f"FREE ({left} trial sheet{'s' if left > 1 else ''} left)"
        return False, "Free trial limit reached (2 sheets used). Please upgrade to PRO (300 Tk/mo) to continue."


def increment_sheet_usage(user_id):
    with get_db() as conn:
        conn.execute("""
        UPDATE users 
        SET free_sheets_used = free_sheets_used + 1 
        WHERE id = ? AND plan != 'pro' AND role != 'admin'
        """, (user_id,))
        conn.commit()


def submit_payment_request(user_id, username, phone, trx_id, screenshot_bytes=None, ext=".png"):
    filename = None
    if screenshot_bytes:
        filename = f"pay_{user_id}_{int(datetime.now().timestamp())}{ext}"
        filepath = UPLOAD_DIR / filename
        filepath.write_bytes(screenshot_bytes)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO payments (user_id, username, phone, amount, trx_id, screenshot_path, status)
        VALUES (?, ?, ?, 300, ?, ?, 'pending')
        """, (user_id, username, phone, trx_id, filename))
        conn.commit()
        return cur.lastrowid


def list_users():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, role, status, plan, free_sheets_used, pro_expires_at, created_at FROM users ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]


def update_user_status(user_id, status=None, plan=None, pro_days=30):
    with get_db() as conn:
        cur = conn.cursor()
        if status:
            cur.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
        if plan:
            exp_date = (datetime.now() + timedelta(days=pro_days)).strftime("%Y-%m-%d %H:%M:%S") if plan == "pro" else None
            cur.execute("UPDATE users SET plan = ?, pro_expires_at = ? WHERE id = ?", (plan, exp_date, user_id))
        conn.commit()


def list_payments(status_filter=None):
    with get_db() as conn:
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT * FROM payments WHERE status = ? ORDER BY id DESC", (status_filter,))
        else:
            cur.execute("SELECT * FROM payments ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]


def review_payment(payment_id, approve=True, notes=""):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        pay = cur.fetchone()
        if not pay:
            return False, "Payment request not found"
        new_status = "approved" if approve else "declined"
        cur.execute("""
        UPDATE payments SET status = ?, admin_notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (new_status, notes, payment_id))

        if approve:
            # Grant 30 days Pro
            exp_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
            UPDATE users SET plan = 'pro', status = 'active', pro_expires_at = ? WHERE id = ?
            """, (exp_date, pay["user_id"]))

        conn.commit()
        return True, new_status



TAMPER_LOCK_FILE = DB_DIR / ".tamper_lock"


def is_system_tampered():
    return TAMPER_LOCK_FILE.exists()


def set_tamper_lock(reason="Integrity violation detected"):
    try:
        TAMPER_LOCK_FILE.write_text(f"TAMPER_LOCKED: {reason} at {datetime.now().isoformat()}", encoding="utf-8")
        with get_db() as conn:
            conn.execute("UPDATE users SET status = 'tamper_locked'")
            conn.commit()
    except Exception:
        pass


def delete_user(user_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM payments WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True


def change_password(user_id, new_password):
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters."
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(new_password, salt)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pwd_hash, salt, user_id))
        conn.commit()
        return True, "Password updated successfully."


def get_admin_stats():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'banned'")
        blocked_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE plan = 'pro'")
        pro_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'")
        total_revenue = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(free_sheets_used), 0) FROM users")
        total_sheets = cur.fetchone()[0]
        return {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "pro_users": pro_users,
            "pending_payments": pending_payments,
            "total_revenue": total_revenue,
            "total_sheets": total_sheets,
        }

# Auto initialize DB upon import
init_db()
