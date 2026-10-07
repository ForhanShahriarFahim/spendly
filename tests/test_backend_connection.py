import re
from datetime import datetime

from database.db import (
    _assign_percentages,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_profile,
)


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def add_expense(user_id, amount, category, day="2026-01-01", description="x"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def demo_id():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
    finally:
        conn.close()


def new_user(name="New User", email="new@example.com"):
    return create_user(name, email, "password123")


def pcts(user_id):
    return [row["pct"] for row in get_category_breakdown(user_id)]


# ------------------------------------------------------------ user profile

def test_user_profile_demo_user(client):
    profile = get_user_profile(demo_id())
    assert profile["name"] == "Demo User"
    assert profile["email"] == "demo@spendly.com"
    expected = datetime.strptime(
        profile["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
    assert profile["member_since"] == expected


def test_user_profile_unknown_id_is_none(client):
    assert get_user_profile(99999) is None


# ----------------------------------------------------------------- summary

def test_summary_demo_user(client):
    summary = get_expense_summary(demo_id())
    assert summary == {"total": 230.79, "count": 8}


def test_summary_new_user_is_zero(client):
    assert get_expense_summary(new_user()) == {"total": 0, "count": 0}


# ------------------------------------------------------------------ recent

def test_recent_expenses_demo_user_newest_first(client):
    rows = get_recent_expenses(demo_id())
    assert len(rows) == 8
    assert {"date", "description", "category", "amount"} <= set(rows[0].keys())
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates, reverse=True)


def test_recent_expenses_new_user_empty(client):
    assert get_recent_expenses(new_user()) == []


# --------------------------------------------------------------- breakdown

def test_breakdown_demo_user(client):
    rows = get_category_breakdown(demo_id())
    assert len(rows) == 7
    assert rows[0]["category"] == "Bills"
    totals = [row["total"] for row in rows]
    assert totals == sorted(totals, reverse=True)
    assert all(isinstance(row["pct"], int) for row in rows)
    assert [row["pct"] for row in rows] == [37, 22, 19, 11, 6, 3, 2]
    assert sum(row["pct"] for row in rows) == 100


def test_breakdown_new_user_empty(client):
    assert get_category_breakdown(new_user()) == []


def test_percentages_remainder_goes_to_largest(client):
    user_id = new_user()
    for category in ("Bills", "Food", "Health"):
        add_expense(user_id, 10, category)
    assert pcts(user_id) == [34, 33, 33]


def test_percentages_round_half_up(client):
    user_id = new_user()
    add_expense(user_id, 12.5, "Food")
    add_expense(user_id, 87.5, "Bills")
    # 87.5 -> 88 and 12.5 -> 13 (half-up) overshoot to 101; Bills gives one back.
    assert pcts(user_id) == [87, 13]


def test_percentages_single_category(client):
    user_id = new_user()
    add_expense(user_id, 5, "Food")
    add_expense(user_id, 7, "Food")
    assert pcts(user_id) == [100]


def test_percentages_zero_total_does_not_raise(client):
    rows = [{"category": "Food", "total": 0.0, "count": 1}]
    assert _assign_percentages(rows, 0)[0]["pct"] == 0


# ------------------------------------------------------------------ routes

def test_profile_logged_out_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_demo_user_page(client):
    login(client)
    response = client.get("/profile")
    html = response.data.decode()
    assert response.status_code == 200
    assert "Demo User" in html and "demo@spendly.com" in html
    assert "₹230.79" in html
    assert re.search(r'stat-value">8<', html)
    assert re.search(r'stat-value[^>]*>Bills<', html)
    assert html.count('<progress class="category-progress"') == 7
    assert 'category-pct">37%<' in html


def test_profile_new_user_shows_zero_state(client):
    create_user("Fresh", "fresh@example.com", "password123")
    login(client, "fresh@example.com", "password123")
    html = client.get("/profile").data.decode()
    assert "₹0.00" in html
    assert "<progress" not in html
