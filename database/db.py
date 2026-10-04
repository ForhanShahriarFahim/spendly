import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = ("Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    """Exact-match lookup; the caller normalizes (trim + lower-case) the email."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return id, name and email (never the password hash) or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    """Insert a user with a hashed password. Raises sqlite3.IntegrityError
    if the email is already registered."""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_profile(user_id):
    """Return id, name, email and created_at (never the password hash) or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_expense_summary(user_id):
    """Return {"total": float (2dp), "count": int}; zeros when no expenses."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count"
            " FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return {"total": round(row["total"], 2), "count": row["count"]}
    finally:
        conn.close()


def get_category_breakdown(user_id):
    """Rows of category, total and count, highest total first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS count"
            " FROM expenses WHERE user_id = ?"
            " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=10):
    """Most recent expenses first (date, then id, descending)."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description"
            " FROM expenses WHERE user_id = ?"
            " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()


def _seed_dates(today):
    # Spread 8 dates from the 1st through today — never in the future.
    return [today.replace(day=1 + (i * (today.day - 1)) // 7).isoformat()
            for i in range(8)]


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid
        samples = [
            (12.50, "Food", "Lunch"),
            (3.75, "Transport", "Bus fare"),
            (85.00, "Bills", "Electricity"),
            (24.99, "Health", "Pharmacy"),
            (15.00, "Entertainment", "Movie"),
            (49.90, "Shopping", "Shoes"),
            (7.25, "Other", "Misc"),
            (32.40, "Food", "Groceries"),
        ]
        dates = _seed_dates(date.today())
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [(user_id, amount, category, day, description)
             for (amount, category, description), day in zip(samples, dates)],
        )
        conn.commit()
    finally:
        conn.close()
