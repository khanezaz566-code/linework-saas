"""Database & Authentication Manager for Linework AI SaaS
Handles SQLite persistence for:
- User accounts (Name, Phone, WhatsApp, Password)
- Free Trial Quotas (3 icon sets for Redraw, 10 backgrounds for BG Studio)
- Paid Subscriptions (Redraw Pro: 300 Tk, BG Studio Pro: 200 Tk, Bundle Pro: 500 Tk)
- bKash Manual Payment Requests (Send Money to 01794590310, TrxID verification, Admin Approvals)
- Admin Portal Controller & Analytics
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

# Official Support & Payment Number
BKASH_NUMBER = "01794590310"
SUPPORT_PHONE = "01794590310"
SUPPORT_WHATSAPP = "01794590310"

# Plan Definitions
PLANS = {
    "free": {"name": "Free Trial", "price": 0, "sheets_limit": 3, "bg_limit": 10},
    "redraw_pro": {"name": "Icon Redraw Pro", "price": 300, "sheets_limit": -1, "bg_limit": 10},
    "bg_pro": {"name": "BG Studio Pro", "price": 200, "sheets_limit": 3, "bg_limit": -1},
    "bundle_pro": {"name": "All-In-One Bundle Pro", "price": 500, "sheets_limit": -1, "bg_limit": -1},
    "pro": {"name": "Legacy Pro", "price": 500, "sheets_limit": -1, "bg_limit": -1},
}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_db(conn):
    """Safely apply column additions to existing SQLite tables."""
    cur = conn.cursor()
    # Check users table columns
    cur.execute("PRAGMA table_info(users)")
    existing_user_cols = {row["name"] for row in cur.fetchall()}
    
    needed_user_cols = {
        "name": "TEXT",
        "phone": "TEXT",
        "whatsapp": "TEXT",
        "free_bg_used": "INTEGER DEFAULT 0",
        "last_active": "TEXT"
    }
    for col, col_type in needed_user_cols.items():
        if col not in existing_user_cols:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    # Check payments table columns
    cur.execute("PRAGMA table_info(payments)")
    existing_pay_cols = {row["name"] for row in cur.fetchall()}
    
    needed_pay_cols = {
        "user_name": "TEXT",
        "whatsapp": "TEXT",
        "plan_selected": "TEXT DEFAULT 'bundle_pro'"
    }
    for col, col_type in needed_pay_cols.items():
        if col not in existing_pay_cols:
            try:
                cur.execute(f"ALTER TABLE payments ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    # Ensure admin has phone and name set
    cur.execute("""
    UPDATE users 
    SET phone = ?, name = 'Super Admin', whatsapp = ? 
    WHERE username = 'admin' AND (phone IS NULL OR phone = '')
    """, (BKASH_NUMBER, BKASH_NUMBER))
    
    # Check sessions table columns
    cur.execute("PRAGMA table_info(sessions)")
    existing_sess_cols = {row["name"] for row in cur.fetchall()}
    if "last_seen" not in existing_sess_cols:
        try:
            cur.execute("ALTER TABLE sessions ADD COLUMN last_seen TEXT")
        except Exception:
            pass
    conn.commit()


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT,
            phone TEXT UNIQUE,
            whatsapp TEXT,
            email TEXT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            plan TEXT DEFAULT 'free',
            free_sheets_used INTEGER DEFAULT 0,
            free_bg_used INTEGER DEFAULT 0,
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
            user_name TEXT,
            phone TEXT NOT NULL,
            whatsapp TEXT,
            plan_selected TEXT DEFAULT 'bundle_pro',
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

        _migrate_db(conn)

        # Ensure default admin exists
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = 'admin' OR phone = ?", (BKASH_NUMBER,))
        if not cur.fetchone():
            salt = secrets.token_hex(16)
            pwd_hash = _hash_password("admin123", salt)
            cur.execute("""
            INSERT INTO users (username, name, phone, whatsapp, email, password_hash, salt, role, status, plan, pro_expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'admin', 'active', 'bundle_pro', ?)
            """, ("admin", "Super Admin", BKASH_NUMBER, BKASH_NUMBER, "admin@linework.ai", pwd_hash, salt, "2099-12-31 23:59:59"))
            conn.commit()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("880") and len(digits) == 13:
        digits = digits[2:]
    return digits


def register_user(name: str, phone: str, whatsapp: str, password: str):
    """Register a new user with 3 free redraw icon sets & 10 free backgrounds."""
    name = (name or "").strip()
    phone_norm = normalize_phone(phone)
    wp_norm = normalize_phone(whatsapp) or phone_norm
    password = (password or "").strip()

    if not name:
        return None, "Please provide your full name."
    if len(phone_norm) < 11:
        return None, "Please provide a valid 11-digit phone number."
    if len(password) < 4:
        return None, "Password must be at least 4 characters."

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE phone = ? OR username = ?", (phone_norm, phone_norm))
        if cur.fetchone():
            return None, "An account with this phone number already exists. Please sign in."

        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(password, salt)
        cur.execute("""
        INSERT INTO users (username, name, phone, whatsapp, password_hash, salt, role, status, plan, free_sheets_used, free_bg_used)
        VALUES (?, ?, ?, ?, ?, ?, 'user', 'active', 'free', 0, 0)
        """, (phone_norm, name, phone_norm, wp_norm, pwd_hash, salt))
        conn.commit()
        user_id = cur.lastrowid
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = dict(cur.fetchone())
        return user_row, None


def authenticate_user(identifier: str, password: str):
    """Authenticate user using Phone or Username."""
    raw_ident = (identifier or "").strip()
    phone_norm = normalize_phone(raw_ident)
    password = (password or "").strip()

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM users 
        WHERE phone = ? OR username = ? OR email = ?
        """, (phone_norm or raw_ident, raw_ident, raw_ident))
        user = cur.fetchone()
        if not user:
            return None, "User not found with this phone number or username."

        u_dict = dict(user)
        if u_dict["status"] == "banned":
            return None, "Your account has been suspended. Please contact support at 01794590310."

        pwd_hash = _hash_password(password, u_dict["salt"])
        if pwd_hash != u_dict["password_hash"]:
            return None, "Incorrect password."

        # Check and handle expiration
        _check_pro_expiration(u_dict, conn)
        return u_dict, None


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    with get_db() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        conn.commit()
    return token


def get_user_from_token(token: str):
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
        u_dict = dict(user)
        _check_pro_expiration(u_dict, conn)
        
        # Keep activity timestamp fresh
        try:
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE sessions SET last_seen = ? WHERE token = ?", (now_iso, token))
            conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (now_iso, u_dict["id"]))
            conn.commit()
        except Exception:
            pass
        return u_dict


def delete_session(token: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def _check_pro_expiration(u_dict: dict, conn):
    """Automatically downgrade plan to 'free' if pro expired and not admin."""
    if u_dict.get("role") == "admin":
        return
    plan = u_dict.get("plan", "free")
    exp_str = u_dict.get("pro_expires_at")
    if plan in ("redraw_pro", "bg_pro", "bundle_pro", "pro") and exp_str:
        try:
            exp_dt = datetime.fromisoformat(exp_str)
            if datetime.now() > exp_dt:
                conn.execute("UPDATE users SET plan = 'free' WHERE id = ?", (u_dict["id"],))
                conn.commit()
                u_dict["plan"] = "free"
        except Exception:
            pass


def get_user_quota_info(user_dict: dict) -> dict:
    """Format user quota status for frontend indicators and gatekeeping."""
    plan = user_dict.get("plan", "free")
    role = user_dict.get("role", "user")
    is_admin = (role == "admin")

    sheets_used = int(user_dict.get("free_sheets_used") or 0)
    bg_used = int(user_dict.get("free_bg_used") or 0)

    # Redraw capability
    if is_admin or plan in ("bundle_pro", "redraw_pro", "pro"):
        can_redraw = True
        sheets_left = "Unlimited"
    else:
        can_redraw = (sheets_used < 3)
        sheets_left = max(0, 3 - sheets_used)

    # BG Studio capability
    if is_admin or plan in ("bundle_pro", "bg_pro", "pro"):
        can_bg = True
        bg_left = "Unlimited"
    else:
        can_bg = (bg_used < 10)
        bg_left = max(0, 10 - bg_used)

    return {
        "id": user_dict["id"],
        "name": user_dict.get("name") or user_dict.get("username"),
        "phone": user_dict.get("phone") or "",
        "whatsapp": user_dict.get("whatsapp") or user_dict.get("phone") or "",
        "role": role,
        "status": user_dict.get("status", "active"),
        "plan": plan,
        "plan_name": PLANS.get(plan, {}).get("name", "Free Trial"),
        "pro_expires_at": user_dict.get("pro_expires_at"),
        "sheets_used": sheets_used,
        "sheets_limit": 3,
        "sheets_left": sheets_left,
        "can_redraw": can_redraw,
        "bg_used": bg_used,
        "bg_limit": 10,
        "bg_left": bg_left,
        "can_bg": can_bg,
        "bkash_number": BKASH_NUMBER,
        "support_phone": SUPPORT_PHONE,
    }


def can_user_process_sheet(user_id: int):
    """Check Redraw permission: Free limit 3 icon sets, or Redraw/Bundle Pro."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        if not u:
            return False, "User not found"
        u_dict = dict(u)
        _check_pro_expiration(u_dict, conn)

        if u_dict["status"] != "active":
            return False, "Account suspended. Contact support at 01794590310."

        if u_dict["role"] == "admin" or u_dict["plan"] in ("bundle_pro", "redraw_pro", "pro"):
            return True, "PRO (Unlimited Redraw)"

        used = int(u_dict.get("free_sheets_used") or 0)
        if used < 3:
            left = 3 - used
            return True, f"FREE ({left} trial sheet{'s' if left > 1 else ''} left)"

        return False, "Free trial limit reached (3 icon sets used). Upgrade to Icon Redraw Pro (300 Tk/mo) or All-In-One Bundle (500 Tk/mo) to continue."


def increment_sheet_usage(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, plan FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        if not u:
            return
        if u["role"] == "admin" or u["plan"] in ("bundle_pro", "redraw_pro", "pro"):
            return
        conn.execute("UPDATE users SET free_sheets_used = free_sheets_used + 1 WHERE id = ?", (user_id,))
        conn.commit()


def can_user_process_bg(user_id: int):
    """Check BG Studio permission: Free limit 10 backgrounds, or BG/Bundle Pro."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        if not u:
            return False, "User not found"
        u_dict = dict(u)
        _check_pro_expiration(u_dict, conn)

        if u_dict["status"] != "active":
            return False, "Account suspended. Contact support at 01794590310."

        if u_dict["role"] == "admin" or u_dict["plan"] in ("bundle_pro", "bg_pro", "pro"):
            return True, "PRO (Unlimited BG Studio)"

        used = int(u_dict.get("free_bg_used") or 0)
        if used < 10:
            left = 10 - used
            return True, f"FREE ({left} trial background{'s' if left > 1 else ''} left)"

        return False, "Free trial limit reached (10 backgrounds used). Upgrade to BG Studio Pro (200 Tk/mo) or All-In-One Bundle (500 Tk/mo) to continue."


def increment_bg_usage(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, plan FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        if not u:
            return
        if u["role"] == "admin" or u["plan"] in ("bundle_pro", "bg_pro", "pro"):
            return
        conn.execute("UPDATE users SET free_bg_used = free_bg_used + 1 WHERE id = ?", (user_id,))
        conn.commit()


def submit_payment_request(user_id: int, plan_selected: str, amount: int, phone: str, trx_id: str, screenshot_bytes=None, ext=".png"):
    filename = None
    if screenshot_bytes:
        filename = f"pay_{user_id}_{int(datetime.now().timestamp())}{ext}"
        filepath = UPLOAD_DIR / filename
        filepath.write_bytes(screenshot_bytes)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, name, whatsapp FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        uname = u["username"] if u else "user"
        fullname = (u["name"] if u and u["name"] else uname)
        u_wp = (u["whatsapp"] if u and u["whatsapp"] else phone)

        cur.execute("""
        INSERT INTO payments (user_id, username, user_name, phone, whatsapp, plan_selected, amount, trx_id, screenshot_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (user_id, uname, fullname, phone, u_wp, plan_selected, amount, trx_id.strip().upper(), filename))
        conn.commit()
        return cur.lastrowid



def grant_user_access(user_id: int, plan: str, days: int = 30, role: str = "user", status: str = "active", reset_quota: bool = False, sheets_used: int = None, bg_used: int = None):
    with get_db() as conn:
        cur = conn.cursor()
        now = datetime.now()
        
        # Expiry date computation
        if plan in ("bundle_pro", "redraw_pro", "bg_pro", "pro"):
            if days >= 3650 or days == -1:
                exp_date = "2099-12-31 23:59:59"
            else:
                exp_date = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            exp_date = None
            
        cur.execute("""
        UPDATE users 
        SET plan = ?, pro_expires_at = ?, role = ?, status = ?
        WHERE id = ?
        """, (plan, exp_date, role, status, user_id))
        
        if reset_quota:
            cur.execute("UPDATE users SET free_sheets_used = 0, free_bg_used = 0 WHERE id = ?", (user_id,))
        else:
            if sheets_used is not None:
                cur.execute("UPDATE users SET free_sheets_used = ? WHERE id = ?", (int(sheets_used), user_id))
            if bg_used is not None:
                cur.execute("UPDATE users SET free_bg_used = ? WHERE id = ?", (int(bg_used), user_id))
                
        conn.commit()
        return True


def list_users(search: str = None, filter_type: str = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = """
        SELECT id, username, name, phone, whatsapp, email, role, status, plan, 
               free_sheets_used, free_bg_used, pro_expires_at, created_at,
               COALESCE(last_active, created_at) AS last_active
        FROM users
        """
        params = []
        conditions = []
        if search:
            s = f"%{search.strip()}%"
            conditions.append("(username LIKE ? OR name LIKE ? OR phone LIKE ? OR whatsapp LIKE ?)")
            params.extend([s, s, s, s])
            
        if filter_type == "pro":
            conditions.append("plan IN ('bundle_pro', 'redraw_pro', 'bg_pro', 'pro')")
        elif filter_type == "free":
            conditions.append("plan = 'free'")
        elif filter_type == "banned":
            conditions.append("status = 'banned'")
        elif filter_type == "admin":
            conditions.append("role = 'admin'")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY id DESC"
        cur.execute(query, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]
        
        # Calculate online status & remaining days for each user
        now = datetime.now()
        for r in rows:
            last_act_str = r.get("last_active")
            is_online = False
            if last_act_str:
                try:
                    last_act_dt = datetime.fromisoformat(last_act_str.replace("Z", ""))
                    if (now - last_act_dt).total_seconds() < 900:  # 15 minutes
                        is_online = True
                except Exception:
                    pass
            r["is_online"] = is_online
            
            exp_str = r.get("pro_expires_at")
            days_left = 0
            if exp_str and r.get("plan") != "free":
                try:
                    exp_dt = datetime.fromisoformat(exp_str)
                    diff = (exp_dt - now).days
                    days_left = max(0, diff) if diff < 20000 else 9999
                except Exception:
                    pass
            r["days_left"] = days_left
            
        if filter_type == "online":
            rows = [r for r in rows if r["is_online"]]
            
        return rows


def get_admin_stats():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'banned'")
        banned_users = cur.fetchone()[0]
        
        # Live active online users (active in last 15 minutes)
        cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM sessions 
        WHERE last_seen >= datetime('now', '-15 minutes')
        """)
        live_online = cur.fetchone()[0] or 0
        live_online = max(live_online, 1)  # At least 1 (the current admin)
        
        # Active Today (last 24 hours)
        cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM sessions 
        WHERE last_seen >= datetime('now', '-24 hours')
        """)
        active_today = max(cur.fetchone()[0] or 0, live_online)
        
        cur.execute("SELECT COUNT(*) FROM users WHERE plan = 'free'")
        free_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE plan = 'redraw_pro'")
        redraw_pro_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE plan = 'bg_pro'")
        bg_pro_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE plan IN ('bundle_pro', 'pro')")
        bundle_pro_users = cur.fetchone()[0]
        
        pro_users = redraw_pro_users + bg_pro_users + bundle_pro_users
        
        # Monthly Recurring Revenue (MRR) projection
        mrr = (redraw_pro_users * 300) + (bg_pro_users * 200) + (bundle_pro_users * 500)
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'")
        total_revenue = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(free_sheets_used), 0) FROM users")
        total_sheets_used = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(free_bg_used), 0) FROM users")
        total_bg_used = cur.fetchone()[0]

        conv_rate = round((pro_users / max(total_users, 1)) * 100, 1)

        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "live_online": live_online,
            "active_today": active_today,
            "free_users": free_users,
            "redraw_pro_users": redraw_pro_users,
            "bg_pro_users": bg_pro_users,
            "bundle_pro_users": bundle_pro_users,
            "pro_users": pro_users,
            "mrr": mrr,
            "conv_rate": conv_rate,
            "pending_payments": pending_payments,
            "total_revenue": total_revenue,
            "total_sheets_used": total_sheets_used,
            "total_bg_used": total_bg_used,
            "bkash_number": BKASH_NUMBER,
            "support_phone": SUPPORT_PHONE,
        }


# Auto initialize DB upon import
init_db()
