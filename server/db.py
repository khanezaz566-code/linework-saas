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
from datetime import datetime, timedelta, date
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or os.environ.get("POSTGRES_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = bool(DATABASE_URL and PSYCOPG2_AVAILABLE)


class PgRow(dict):
    """Dictionary-like and tuple-like row wrapper for PostgreSQL cursor results.
    Ensures datetime and Decimal fields serialize seamlessly to JSON without 500 errors.
    """
    def __init__(self, cur, row):
        if row is None:
            super().__init__()
            self._vals = []
            return
        desc = getattr(cur, "description", None)
        if desc:
            cols = [d[0] for d in desc]
        else:
            cols = [f"col_{i}" for i in range(len(row))]
        cleaned = []
        for v in row:
            if isinstance(v, (datetime, date)):
                cleaned.append(v.strftime("%Y-%m-%d %H:%M:%S"))
            elif hasattr(v, "as_tuple"):
                cleaned.append(float(v))
            else:
                cleaned.append(v)
        super().__init__(zip(cols, cleaned))
        self._vals = cleaned

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key)


class PostgresCursorWrapper:
    def __init__(self, cur):
        self.cur = cur
        self.lastrowid = None

    @property
    def description(self):
        return self.cur.description

    @property
    def rowcount(self):
        return self.cur.rowcount

    def _wrap(self, row):
        if row is None:
            return None
        return PgRow(self.cur, row)

    def execute(self, query, params=None):
        pg_query = query.replace("?", "%s")
        upper = pg_query.strip().upper()
        if upper.startswith("INSERT INTO") and ("users" in upper.lower() or "payments" in upper.lower()) and "RETURNING" not in upper:
            pg_query = pg_query.rstrip(" ;") + " RETURNING id"
            if params:
                self.cur.execute(pg_query, params)
            else:
                self.cur.execute(pg_query)
            try:
                row = self.cur.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                pass
            return self

        if params:
            self.cur.execute(pg_query, params)
        else:
            self.cur.execute(pg_query)
        return self

    def fetchone(self):
        row = self.cur.fetchone()
        return self._wrap(row)

    def fetchall(self):
        rows = self.cur.fetchall()
        return [self._wrap(r) for r in rows]

    def close(self):
        try:
            self.cur.close()
        except Exception:
            pass

    def __iter__(self):
        for r in self.cur:
            yield self._wrap(r)


class PostgresConnectionWrapper:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self.raw_conn.cursor())

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def executescript(self, script):
        cur = self.raw_conn.cursor()
        cur.execute(script)
        self.raw_conn.commit()
        cur.close()

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

    def close(self):
        self.raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self.rollback()
            except Exception:
                pass
        else:
            try:
                self.commit()
            except Exception:
                pass
        try:
            self.close()
        except Exception:
            pass


def _get_pg_conn():
    url = DATABASE_URL
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return psycopg2.connect(url, connect_timeout=3)

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
    global IS_POSTGRES
    if IS_POSTGRES:
        try:
            return PostgresConnectionWrapper(_get_pg_conn())
        except Exception as e:
            print(f"[DB WARN] Failed to connect to Postgres ({e}), falling back to SQLite permanently", file=sys.stderr)
            IS_POSTGRES = False
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _safe_add_column(conn, table: str, col: str, col_type: str):
    if IS_POSTGRES:
        try:
            cur = conn.cursor()
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    else:
        try:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = {row["name"] for row in cur.fetchall()}
            if col not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                conn.commit()
        except Exception:
            pass


def _migrate_db(conn):
    """Safely apply column additions to existing tables."""
    # Ensure users table columns exist
    needed_user_cols = {
        "name": "TEXT",
        "phone": "TEXT",
        "whatsapp": "TEXT",
        "free_bg_used": "INTEGER DEFAULT 0",
        "last_active": "TEXT",
        "last_seen_epoch": "BIGINT DEFAULT 0",
        "email": "TEXT",
        "provider": "TEXT DEFAULT 'direct'",
        "social_id": "TEXT"
    }
    for col, col_type in needed_user_cols.items():
        _safe_add_column(conn, "users", col, col_type)

    # Ensure payments table columns exist
    needed_pay_cols = {
        "user_name": "TEXT",
        "whatsapp": "TEXT",
        "plan_selected": "TEXT DEFAULT 'bundle_pro'",
        "admin_notes": "TEXT",
        "reviewed_at": "TEXT",
        "updated_at": "TEXT"
    }
    for col, col_type in needed_pay_cols.items():
        _safe_add_column(conn, "payments", col, col_type)

    # Ensure sessions table columns exist
    needed_sess_cols = {
        "last_seen": "TEXT",
        "last_seen_epoch": "BIGINT DEFAULT 0"
    }
    for col, col_type in needed_sess_cols.items():
        _safe_add_column(conn, "sessions", col, col_type)

    # Ensure admin has phone and name set
    try:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users 
        SET phone = ?, name = 'Super Admin', whatsapp = ? 
        WHERE username = 'admin' AND (phone IS NULL OR phone = '')
        """, (BKASH_NUMBER, BKASH_NUMBER))
        
        # Auto-grant admin role to Ezaz account
        cur.execute("""
        UPDATE users 
        SET role = 'admin', plan = 'bundle_pro', pro_expires_at = '2099-12-31 23:59:59'
        WHERE username = 'admin' OR phone = ? OR LOWER(name) = 'ezaz' OR username = '9872546789087654'
        """, (BKASH_NUMBER,))
        conn.commit()
    except Exception:
        if IS_POSTGRES:
            try:
                conn.rollback()
            except Exception:
                pass


def init_db():
    global IS_POSTGRES
    try:
        with get_db() as conn:
            if IS_POSTGRES:
                cur = conn.cursor()
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TEXT,
                    last_seen_epoch BIGINT DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    last_seen TEXT,
                    last_seen_epoch BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
                    reviewed_at TEXT
                );
                """)
                conn.commit()
            else:
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

            # Ensure default admin exists and is ALWAYS active admin with bundle_pro
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = 'admin' OR phone = ?", (BKASH_NUMBER,))
            adm_row = cur.fetchone()
            if not adm_row:
                salt = secrets.token_hex(16)
                pwd_hash = _hash_password("admin123", salt)
                cur.execute("""
                INSERT INTO users (username, name, phone, whatsapp, email, password_hash, salt, role, status, plan, pro_expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'admin', 'active', 'bundle_pro', ?)
                """, ("admin", "Super Admin", BKASH_NUMBER, BKASH_NUMBER, "admin@linework.ai", pwd_hash, salt, "2099-12-31 23:59:59"))
                conn.commit()
            else:
                cur.execute("""
                UPDATE users
                SET role = 'admin', status = 'active', plan = 'bundle_pro', pro_expires_at = '2099-12-31 23:59:59'
                WHERE id = ?
                """, (adm_row[0],))
                conn.commit()
    except Exception as e:
        print(f"[DB WARN] Error initializing DB with IS_POSTGRES={IS_POSTGRES}: {e}. Retrying with SQLite fallback...", file=sys.stderr)
        IS_POSTGRES = False
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
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


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("880") and len(digits) == 13:
        digits = digits[2:]
    return digits


def register_user(name: str, phone: str, whatsapp: str, password: str, email: str = "", provider: str = "direct", social_id: str = ""):
    """Register a new user with 3 free redraw icon sets & 10 free backgrounds."""
    name = (name or "").strip()
    phone_norm = normalize_phone(phone)
    wp_norm = normalize_phone(whatsapp) or phone_norm
    password = (password or "").strip()
    email = (email or "").strip().lower()

    if not name:
        return None, "Please provide your full name."
    if len(phone_norm) < 6 and not email:
        return None, "Please provide a valid phone number or WhatsApp."
    if not password and not social_id:
        return None, "Password must be at least 4 characters."
    if password and len(password) < 4:
        return None, "Password must be at least 4 characters."

    # fallback identifier if phone is missing but email is provided
    ident = phone_norm or email or f"user_{secrets.token_hex(4)}"
    if not phone_norm and email:
        phone_norm = ident
    if not wp_norm:
        wp_norm = phone_norm
    if not password:
        password = secrets.token_hex(8)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM users 
        WHERE (phone IS NOT NULL AND phone != '' AND phone = ?) 
           OR (username IS NOT NULL AND username = ?)
           OR (email IS NOT NULL AND email != '' AND email = ?)
        """, (phone_norm, ident, email or ident))
        existing = cur.fetchone()
        if existing:
            u_dict = dict(existing)
            _check_pro_expiration(u_dict, conn)
            # If user already exists, update name/whatsapp if provided, and log them in
            try:
                conn.execute("""
                UPDATE users SET name = COALESCE(NULLIF(?, ''), name), 
                                 whatsapp = COALESCE(NULLIF(?, ''), whatsapp),
                                 last_active = ?, last_seen_epoch = ?
                WHERE id = ?
                """, (name, wp_norm, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(datetime.now().timestamp()), u_dict["id"]))
                conn.commit()
                cur.execute("SELECT * FROM users WHERE id = ?", (u_dict["id"],))
                u_dict = dict(cur.fetchone())
            except Exception:
                pass
            return u_dict, None

        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(password, salt)
        now_epoch = int(datetime.now().timestamp())
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Discover available columns dynamically for 100% database compatibility
        avail_cols = set()
        try:
            if IS_POSTGRES:
                cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_name = 'users'")
            else:
                cur.execute("PRAGMA table_info(users)")
            avail_cols = {row["name"] for row in cur.fetchall()}
        except Exception:
            if IS_POSTGRES:
                try:
                    conn.rollback()
                except Exception:
                    pass

        user_data = {
            "username": ident,
            "name": name,
            "phone": phone_norm,
            "whatsapp": wp_norm,
            "password_hash": pwd_hash,
            "salt": salt,
            "role": "user",
            "status": "active",
            "plan": "free",
            "free_sheets_used": 0,
            "free_bg_used": 0,
            "last_active": now_iso,
            "last_seen_epoch": now_epoch,
            "email": email,
            "provider": provider,
            "social_id": social_id
        }

        cols_to_insert = [c for c in user_data if not avail_cols or c in avail_cols]
        if not cols_to_insert:
            cols_to_insert = ["username", "name", "phone", "whatsapp", "password_hash", "salt", "role", "status", "plan", "free_sheets_used", "free_bg_used", "last_active", "last_seen_epoch"]

        placeholders = ", ".join(["?"] * len(cols_to_insert))
        col_names = ", ".join(cols_to_insert)
        vals = tuple(user_data[c] for c in cols_to_insert)

        cur.execute(f"INSERT INTO users ({col_names}) VALUES ({placeholders})", vals)
        conn.commit()

        cur.execute("SELECT * FROM users WHERE username = ? OR phone = ?", (ident, phone_norm))
        user_row = cur.fetchone()
        if user_row:
            return dict(user_row), None
        return None, "Failed to create account. Please try again."


def social_authenticate_or_register(provider: str, social_id: str, email: str, name: str, phone: str = "", whatsapp: str = "", password: str = ""):
    """Authenticate or register user via Google or Facebook social login."""
    provider = (provider or "google").lower()
    email = (email or "").strip().lower()
    name = (name or "").strip() or ("Google User" if provider == "google" else "Facebook User")
    phone_norm = normalize_phone(phone)
    wp_norm = normalize_phone(whatsapp) or phone_norm

    with get_db() as conn:
        cur = conn.cursor()
        # Look up by social_id, email, or phone
        cur.execute("""
        SELECT * FROM users 
        WHERE (social_id IS NOT NULL AND social_id != '' AND social_id = ?)
           OR (email IS NOT NULL AND email != '' AND email = ?)
           OR (phone IS NOT NULL AND phone != '' AND phone = ?)
        """, (social_id or "NONE", email or "NONE", phone_norm or "NONE"))
        user = cur.fetchone()
        if user:
            u_dict = dict(user)
            _check_pro_expiration(u_dict, conn)
            # Update missing social info
            try:
                conn.execute("""
                UPDATE users SET social_id = COALESCE(NULLIF(?, ''), social_id),
                                 provider = COALESCE(NULLIF(?, ''), provider),
                                 name = COALESCE(NULLIF(?, ''), name),
                                 whatsapp = COALESCE(NULLIF(?, ''), whatsapp),
                                 last_active = ?, last_seen_epoch = ?
                WHERE id = ?
                """, (social_id, provider, name, wp_norm, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(datetime.now().timestamp()), u_dict["id"]))
                conn.commit()
                cur.execute("SELECT * FROM users WHERE id = ?", (u_dict["id"],))
                u_dict = dict(cur.fetchone())
            except Exception:
                pass
            return u_dict, None

        # New registration with trial
        return register_user(
            name=name,
            phone=phone_norm,
            whatsapp=wp_norm,
            password=password or secrets.token_hex(8),
            email=email,
            provider=provider,
            social_id=social_id
        )


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
    now_epoch = int(datetime.now().timestamp())
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("INSERT INTO sessions (token, user_id, last_seen, last_seen_epoch) VALUES (?, ?, ?, ?)", (token, user_id, now_iso, now_epoch))
        conn.execute("UPDATE users SET last_active = ?, last_seen_epoch = ? WHERE id = ?", (now_iso, now_epoch, user_id))
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
        
        # Keep activity timestamp fresh (both iso string and epoch integer)
        try:
            now_epoch = int(datetime.now().timestamp())
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE sessions SET last_seen = ?, last_seen_epoch = ? WHERE token = ?", (now_iso, now_epoch, token))
            conn.execute("UPDATE users SET last_active = ?, last_seen_epoch = ? WHERE id = ?", (now_iso, now_epoch, u_dict["id"]))
            conn.commit()
        except Exception:
            pass
        return u_dict



def update_user_heartbeat(user_id: int, token: str = None):
    now_epoch = int(datetime.now().timestamp())
    with get_db() as conn:
        try:
            conn.execute("UPDATE users SET last_seen_epoch = ? WHERE id = ?", (now_epoch, user_id))
            if token:
                conn.execute("UPDATE sessions SET last_seen_epoch = ? WHERE token = ?", (now_epoch, token))
            conn.commit()
        except Exception:
            pass

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
            exp_clean = str(exp_str).replace(" ", "T")
            if "." in exp_clean:
                exp_clean = exp_clean.split(".")[0]
            exp_dt = datetime.fromisoformat(exp_clean)
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

    # Redraw capability & limits
    is_redraw_unlimited = (is_admin or plan in ("bundle_pro", "redraw_pro", "pro"))
    if is_redraw_unlimited:
        can_redraw = True
        sheets_left = "Unlimited"
        sheets_limit = -1
    else:
        can_redraw = (sheets_used < 3)
        sheets_left = max(0, 3 - sheets_used)
        sheets_limit = 3

    # BG Studio capability & limits
    is_bg_unlimited = (is_admin or plan in ("bundle_pro", "bg_pro", "pro"))
    if is_bg_unlimited:
        can_bg = True
        bg_left = "Unlimited"
        bg_limit = -1
    else:
        can_bg = (bg_used < 10)
        bg_left = max(0, 10 - bg_used)
        bg_limit = 10

    exp_str = user_dict.get("pro_expires_at")
    days_left = None
    if exp_str:
        try:
            exp_clean = str(exp_str).replace(" ", "T")
            if "." in exp_clean:
                exp_clean = exp_clean.split(".")[0]
            exp_dt = datetime.fromisoformat(exp_clean)
            diff = (exp_dt - datetime.now()).days
            days_left = max(0, diff) if diff < 20000 else 9999
        except Exception:
            days_left = None

    # Human-readable plan badge & display text
    if is_admin:
        plan_badge_text = "👑 Super Admin"
        header_quota_text = "⚡ Super Admin (Unlimited)"
    elif plan in ("bundle_pro", "pro"):
        plan_badge_text = "👑 All-In-One Pro"
        header_quota_text = "👑 All-In-One: Unlimited"
    elif plan == "redraw_pro":
        plan_badge_text = "⚡ Redraw Pro"
        header_quota_text = "👑 Redraw: Unlimited"
    elif plan == "bg_pro":
        plan_badge_text = "🎨 BG Studio Pro"
        header_quota_text = "🎨 BG Studio: Unlimited"
    else:
        plan_badge_text = "Free Trial"
        header_quota_text = f"Trial: {sheets_left}/3 Icons · {bg_left}/10 BG"

    return {
        "id": user_dict["id"],
        "name": user_dict.get("name") or user_dict.get("username"),
        "phone": user_dict.get("phone") or "",
        "whatsapp": user_dict.get("whatsapp") or user_dict.get("phone") or "",
        "role": role,
        "status": user_dict.get("status", "active"),
        "plan": plan,
        "plan_name": PLANS.get(plan, {}).get("name", "Free Trial"),
        "plan_badge_text": plan_badge_text,
        "header_quota_text": header_quota_text,
        "is_redraw_unlimited": is_redraw_unlimited,
        "is_bg_unlimited": is_bg_unlimited,
        "is_bundle": (is_admin or plan in ("bundle_pro", "pro")),
        "pro_expires_at": exp_str,
        "days_left": days_left,
        "sheets_used": sheets_used,
        "sheets_limit": sheets_limit,
        "sheets_left": sheets_left,
        "can_redraw": can_redraw,
        "bg_used": bg_used,
        "bg_limit": bg_limit,
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



def grant_user_access(user_id: int, plan: str = None, days: int = 30, role: str = None, status: str = None, reset_quota: bool = False, sheets_used: int = None, bg_used: int = None):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT plan, role, status, phone, username, pro_expires_at FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return False
        curr = dict(row)
        
        target_plan = plan if plan is not None else curr["plan"]
        target_role = role if role is not None else curr["role"]
        target_status = status if status is not None else curr["status"]

        # Protect Super Admin from accidental demotion or suspension
        if str(curr["phone"]) == str(BKASH_NUMBER) or curr["username"] == "admin" or user_id == 1:
            target_role = "admin"
            target_status = "active"
            if target_plan == "free":
                target_plan = "bundle_pro" 
        
        now = datetime.now()
        if target_plan in ("bundle_pro", "redraw_pro", "bg_pro", "pro"):
            if days >= 3650 or days == -1:
                exp_date = "2099-12-31 23:59:59"
            else:
                base = now
                if curr.get("pro_expires_at") and curr.get("plan") == target_plan:
                    try:
                        clean_curr = str(curr["pro_expires_at"]).replace(" ", "T")
                        if "." in clean_curr:
                            clean_curr = clean_curr.split(".")[0]
                        c_dt = datetime.fromisoformat(clean_curr)
                        if c_dt > now:
                            base = c_dt
                    except Exception:
                        pass
                exp_date = (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            exp_date = None
            
        cur.execute("""
        UPDATE users
        SET plan = ?, pro_expires_at = ?, role = ?, status = ?
        WHERE id = ?
        """, (target_plan, exp_date, target_role, target_status, user_id))
        
        if reset_quota:
            cur.execute("UPDATE users SET free_sheets_used = 0, free_bg_used = 0 WHERE id = ?", (user_id,))
        else:
            if sheets_used is not None:
                cur.execute("UPDATE users SET free_sheets_used = ? WHERE id = ?", (int(sheets_used), user_id))
            if bg_used is not None:
                cur.execute("UPDATE users SET free_bg_used = ? WHERE id = ?", (int(bg_used), user_id))
                
        if target_status == "banned":
            cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            
        conn.commit()
        return True


def list_users(search: str = None, filter_type: str = None):
    with get_db() as conn:
        cur = conn.cursor()
        query = """
        SELECT id, username, name, phone, whatsapp, email, role, status, plan, 
               free_sheets_used, free_bg_used, pro_expires_at, created_at,
               COALESCE(last_seen_epoch, 0) AS last_seen_epoch,
               COALESCE(last_active, CAST(created_at AS TEXT)) AS last_active
        FROM users
        """
        params = []
        conditions = []
        if search:
            s = f"%{search.strip()}%"
            conditions.append("(username LIKE ? OR name LIKE ? OR phone LIKE ? OR whatsapp LIKE ?)")
            params.extend([s, s, s, s])
            
        if filter_type == "online":
            now_epoch = int(datetime.now().timestamp())
            conditions.append(f"last_seen_epoch >= {now_epoch - 900}")
        elif filter_type == "pro":
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
        
        now_epoch = int(datetime.now().timestamp())
        for r in rows:
            last_epoch = int(r.get("last_seen_epoch") or 0)
            diff = now_epoch - last_epoch if last_epoch > 0 else 9999999
            
            # Presence status
            r["diff_seconds"] = diff
            if diff < 30:
                presence = "online"
                presence_text = "🟢 Live Online (Just now)"
                is_online = True
            elif diff < 75:
                presence = "online"
                presence_text = f"🟢 Live Online ({diff}s ago)"
                is_online = True
            elif diff < 900:
                presence = "away"
                presence_text = f"🟡 Active {diff // 60}m ago"
                is_online = True
            elif diff < 86400:
                presence = "offline"
                presence_text = f"⚪ Active {diff // 3600}h ago"
                is_online = False
            else:
                presence = "offline"
                presence_text = "⚪ Offline"
                is_online = False
                
            r["presence"] = presence
            r["presence_text"] = presence_text
            r["is_online"] = is_online
            
            # Quota info
            sheets_used = int(r.get("free_sheets_used") or 0)
            bg_used = int(r.get("free_bg_used") or 0)
            plan = r.get("plan", "free")
            role = r.get("role", "user")
            is_admin = (role == "admin")

            is_redraw_unlimited = (is_admin or plan in ("bundle_pro", "redraw_pro", "pro"))
            is_bg_unlimited = (is_admin or plan in ("bundle_pro", "bg_pro", "pro"))

            r["is_redraw_unlimited"] = is_redraw_unlimited
            r["is_bg_unlimited"] = is_bg_unlimited
            r["sheets_left"] = "Unlimited" if is_redraw_unlimited else max(0, 3 - sheets_used)
            r["bg_left"] = "Unlimited" if is_bg_unlimited else max(0, 10 - bg_used)
            r["is_trial_exhausted"] = (not is_redraw_unlimited and sheets_used >= 3) and (not is_bg_unlimited and bg_used >= 10)
            
            # Days remaining on pro
            exp_str = r.get("pro_expires_at")
            days_left = 0
            if exp_str and r.get("plan") != "free":
                try:
                    exp_dt = datetime.fromisoformat(exp_str)
                    diff_days = (exp_dt - datetime.now()).days
                    days_left = max(0, diff_days) if diff_days < 20000 else 9999
                except Exception:
                    pass
            r["days_left"] = days_left
            
        if filter_type == "online":
            rows = [r for r in rows if r["is_online"]]
            
        return rows


def get_admin_stats():
    now_epoch = int(datetime.now().timestamp())
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'banned'")
        banned_users = cur.fetchone()[0]
        
        # Real-time online: users seen in last 5 minutes (300 seconds)
        threshold_online = now_epoch - 300
        cur.execute("SELECT COUNT(DISTINCT id) FROM users WHERE last_seen_epoch >= ?", (threshold_online,))
        live_online = cur.fetchone()[0] or 0
        live_online = max(live_online, 1)  # At least 1 (the admin viewing)
        
        # Active Today: users seen in last 24 hours (86400 seconds)
        threshold_24h = now_epoch - 86400
        cur.execute("SELECT COUNT(DISTINCT id) FROM users WHERE last_seen_epoch >= ?", (threshold_24h,))
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
            "db_backend": "postgres" if IS_POSTGRES else "sqlite",
            "db_persistent": IS_POSTGRES,
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


def list_payments(status_filter: str = "all"):
    """Fetch payments for admin approval desk."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
        SELECT id, user_id, username, user_name, phone, whatsapp, 
               plan_selected, amount, trx_id, screenshot_path, status, 
               admin_notes, created_at, reviewed_at
        FROM payments
        """
        params = []
        if status_filter and status_filter != "all":
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY id DESC"
        cur.execute(query, tuple(params))
        return [dict(r) for r in cur.fetchall()]


def review_payment(payment_id: int, approve: bool = True, notes: str = ""):
    """Approve or decline bKash payment and activate subscription."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        p = cur.fetchone()
        if not p:
            return False, "Payment not found"
        p_dict = dict(p)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "approved" if approve else "declined"
        cur.execute("""
        UPDATE payments SET status = ?, admin_notes = ?, reviewed_at = ? WHERE id = ?
        """, (status, notes, now_str, payment_id))
        
        if approve:
            plan = p_dict.get("plan_selected", "bundle_pro")
            user_id = p_dict["user_id"]
            pro_exp = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
            UPDATE users SET plan = ?, pro_expires_at = ?, free_sheets_used = 0, free_bg_used = 0 WHERE id = ?
            """, (plan, pro_exp, user_id))
        conn.commit()
        return True, status


def update_user_plan(user_id: int, plan: str, pro_days: int = 30, reset_quota: bool = False):
    grant_user_access(user_id, plan=plan, days=pro_days, reset_quota=reset_quota)


def update_user_status(user_id: int, status: str = "active"):
    return grant_user_access(user_id, status=status)


def delete_user(user_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM payments WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()