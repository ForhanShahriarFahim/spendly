import os
import sqlite3
from datetime import date, datetime

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


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
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
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
    """Return a dict of id, name, email, created_at and member_since
    ("Month YYYY"), never the password hash; None if the user is missing."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    profile = dict(row)
    profile["member_since"] = _format_member_since(profile["created_at"])
    return profile


def _format_member_since(created_at):
    try:
        return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")
    except (TypeError, ValueError):
        return ""


def _date_filter(date_from, date_to):
    """Return (sql_fragment, params) bounding expenses.date inclusively.
    Only fixed fragments are built here; values are always bound via `?`."""
    sql, params = "", []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    return sql, tuple(params)


def get_expense_summary(user_id, date_from=None, date_to=None):
    """Return {"total": float (2dp), "count": int}; zeros when no expenses.
    Optional ISO date bounds (inclusive) restrict the expenses counted."""
    filter_sql, filter_params = _date_filter(date_from, date_to)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count"
            " FROM expenses WHERE user_id = ?" + filter_sql,
            (user_id, *filter_params),
        ).fetchone()
        return {"total": round(row["total"], 2), "count": row["count"]}
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Dicts of category, total, count and pct (integer share of spending,
    summing to 100), highest total first. Optional inclusive ISO date bounds."""
    filter_sql, filter_params = _date_filter(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS count"
            " FROM expenses WHERE user_id = ?"
            + filter_sql
            + " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id, *filter_params),
        ).fetchall()
    finally:
        conn.close()
    return _assign_percentages(rows, sum(row["total"] for row in rows))


def _assign_percentages(rows, total):
    """Integer percentages (half-up) that sum to exactly 100; the first
    (largest) row absorbs any rounding remainder. All 0 when total <= 0."""
    result = [dict(row) for row in rows]
    for item in result:
        item["pct"] = int(item["total"] * 100 / total + 0.5) if total > 0 else 0
    if result and total > 0:
        result[0]["pct"] += 100 - sum(item["pct"] for item in result)
    return result


def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None):
    """Most recent expenses first (date, then id, descending). Optional
    inclusive ISO date bounds."""
    filter_sql, filter_params = _date_filter(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description"
            " FROM expenses WHERE user_id = ?"
            + filter_sql
            + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *filter_params, limit),
        ).fetchall()
    finally:
        conn.close()


def create_expense(user_id, amount, category, date, description):
    """Insert an expense owned by `user_id` and return its id. A blank
    description is stored as NULL."""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description or None),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_expense(expense_id, user_id):
    """Return the expense row only if it exists and is owned by `user_id`,
    else None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description"
            " FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, date, description):
    """Update an expense owned by `user_id`. Returns True if a row changed,
    False if it does not exist or belongs to someone else. A blank
    description is stored as NULL."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?,"
            " description = ? WHERE id = ? AND user_id = ?",
            (amount, category, date, description or None, expense_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_expense(expense_id, user_id):
    """Delete an expense owned by `user_id`. Returns True if a row was
    removed, False if it does not exist or belongs to someone else."""
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _seed_dates(today):
    # Spread 8 dates from the 1st through today — never in the future.
    return [
        today.replace(day=1 + (i * (today.day - 1)) // 7).isoformat() for i in range(8)
    ]


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
            [
                (user_id, amount, category, day, description)
                for (amount, category, description), day in zip(samples, dates)
            ],
        )
        conn.commit()
    finally:
        conn.close()
