import re
from datetime import datetime
from pathlib import Path

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_profile,
)

ROOT = Path(__file__).resolve().parent.parent


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def add_expense(user_id, amount, category, day, description):
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


def new_user_login(client, name="New User", email="new@example.com"):
    user_id = create_user(name, email, "password123")
    login(client, email, "password123")
    return user_id


def page(client):
    return client.get("/profile").data.decode()


def demo_id():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


# ---------------------------------------------------------------- access

def test_profile_requires_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_stale_session_redirects_and_clears(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_profile_deleted_user_redirects(client):
    user_id = new_user_login(client)
    conn = get_db()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# --------------------------------------------------------------- content

def test_profile_shows_user_details(client):
    login(client)
    response = client.get("/profile")
    html = response.data.decode()
    assert response.status_code == 200
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "Member since" in html


def test_summary_helper_totals():
    assert get_expense_summary(demo_id()) == {"total": 230.79, "count": 8}


def test_profile_shows_total_and_count(client):
    login(client)
    html = page(client)
    assert "230.79" in html
    assert 'class="stat-value">8<' in html


def test_category_breakdown_order():
    rows = get_category_breakdown(demo_id())
    assert [r["category"] for r in rows] == [
        "Bills", "Shopping", "Food", "Health",
        "Entertainment", "Other", "Transport",
    ]
    food = next(r for r in rows if r["category"] == "Food")
    assert round(food["total"], 2) == 44.90
    assert food["count"] == 2


def test_profile_breakdown_rendered_in_order(client):
    login(client)
    html = page(client)
    section = html[html.index("Spending by category"):]
    positions = [section.index(c) for c in ("Bills", "Shopping", "Food", "Health")]
    assert positions == sorted(positions)


def test_profile_section_order(client):
    login(client)
    html = page(client)
    marks = [
        html.index('class="profile-header"'),
        html.index('class="profile-stats"'),
        html.index("Recent expenses"),
        html.index("Spending by category"),
    ]
    assert marks == sorted(marks)


def test_profile_top_category(client):
    login(client)
    html = page(client)
    stats = html[html.index('class="profile-stats"'):html.index("Recent expenses")]
    assert re.search(r'Top category</span>\s*<span class="stat-value stat-value--text"[^>]*>Bills<', stats)


def test_profile_progress_bars(client):
    login(client)
    html = page(client)
    assert html.count('<progress class="category-progress"') == 7
    assert 'style=' not in html


def test_recent_expenses_limit_order_and_format(client):
    user_id = new_user_login(client)
    for i in range(12):
        add_expense(user_id, 5, "Food", f"2026-01-{i + 1:02d}", f"item-{i:02d}")
    html = page(client)
    assert html.count('class="expense-row"') == 10
    assert "item-11" in html and "item-02" in html
    assert "item-01" not in html and "item-00" not in html
    assert html.index("item-11") < html.index("item-10") < html.index("item-02")
    assert "₹5.00" in html


def test_recent_expenses_same_date_tiebreak_by_id():
    user_id = create_user("Tie", "tie@example.com", "password123")
    add_expense(user_id, 1, "Food", "2026-02-01", "first")
    add_expense(user_id, 2, "Food", "2026-02-01", "second")
    rows = get_recent_expenses(user_id)
    assert [r["description"] for r in rows] == ["second", "first"]


def test_profile_new_user_empty_state(client):
    new_user_login(client)
    response = client.get("/profile")
    html = response.data.decode()
    assert response.status_code == 200
    assert "₹0.00" in html
    assert "No expenses yet" in html
    assert 'class="expense-row"' not in html


def test_profile_handles_null_description(client):
    user_id = new_user_login(client)
    add_expense(user_id, 9.5, "Other", "2026-03-01", None)
    assert "—" in page(client)


# ------------------------------------------------------------- isolation

def test_profile_isolation_between_users(client):
    user_id = new_user_login(client)
    add_expense(user_id, 77, "Food", "2026-03-01", "OTHER-USER-SECRET")
    assert "OTHER-USER-SECRET" in page(client)

    client.get("/logout")
    login(client)
    assert "OTHER-USER-SECRET" not in page(client)

    rows = get_recent_expenses(demo_id())
    assert all(r["description"] != "OTHER-USER-SECRET" for r in rows)


# -------------------------------------------------------------- security

def test_profile_does_not_expose_password_hash(client):
    login(client)
    html = page(client)
    assert "password_hash" not in html
    assert "scrypt:" not in html and "pbkdf2:" not in html
    assert "password_hash" not in get_user_profile(demo_id()).keys()


def test_profile_escapes_description(client):
    user_id = new_user_login(client)
    add_expense(user_id, 1, "Other", "2026-03-01", "<script>alert(1)</script>")
    html = page(client)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------- layout

def test_navbar_links_to_profile(client):
    login(client)
    html = client.get("/").data.decode()
    assert '<a href="/profile" class="nav-user">' in html


def test_navbar_shows_username_and_signout(client):
    login(client)
    html = page(client)
    assert 'class="nav-user">Demo User</a>' in html
    assert 'class="nav-signout">Sign out</a>' in html


def test_profile_uses_shared_layout_and_css(client):
    login(client)
    html = page(client)
    assert 'class="navbar"' in html
    assert 'class="footer"' in html
    assert "css/profile.css" in html


def test_new_files_have_no_inline_style_hex_or_hardcoded_urls():
    template = (ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    assert "<style" not in template
    assert "style=" not in template
    assert not re.search(r"#[0-9a-fA-F]{3,8}", template)
    assert 'href="/' not in template
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


# ------------------------------------------------------- design polish

def test_avatar_shows_uppercase_initial(client):
    new_user_login(client, name="alice smith", email="alice@example.com")
    html = page(client)
    assert re.search(r'class="profile-avatar"[^>]*>\s*A\s*</div>', html)


def test_member_since_shows_month_and_year(client):
    user_id = new_user_login(client)
    created = get_user_profile(user_id)["created_at"][:10]
    expected = datetime.strptime(created, "%Y-%m-%d").strftime("%B %Y")
    assert f"Member since {expected}" in page(client)


def test_expense_count_singular_and_plural(client):
    user_id = new_user_login(client)
    add_expense(user_id, 10, "Food", "2026-01-01", "a")
    html = page(client)
    assert "1 expense" in html and "1 expenses" not in html
    add_expense(user_id, 10, "Food", "2026-01-02", "b")
    assert "2 expenses" in page(client)


def test_progress_value_matches_category_share(client):
    user_id = new_user_login(client)
    add_expense(user_id, 75, "Food", "2026-01-01", "a")
    add_expense(user_id, 25, "Bills", "2026-01-02", "b")
    html = page(client)
    values = [float(v) for v in re.findall(r'<progress[^>]*value="([\d.]+)"', html)]
    assert values == [75, 25]
    assert 'category-pct">75%<' in html and 'category-pct">25%<' in html
    assert html.count('max="100"') == 2
    assert "style=" not in html


def test_empty_state_has_no_table_or_breakdown(client):
    new_user_login(client)
    html = page(client)
    assert "No expenses yet" in html
    assert "<table" not in html and "category-progress" not in html
    assert re.search(r'stat-value[^>]*>—<', html)


def test_table_accessibility_markup(client):
    user_id = new_user_login(client)
    add_expense(user_id, 10, "Food", "2026-01-01", "a")
    html = page(client)
    assert "<caption" in html
    assert html.count('scope="col"') == 5
    assert re.search(r'class="expense-table-wrap"[^>]*tabindex="0"', html)


def test_profile_css_design_rules():
    css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    for needle in ("::-webkit-progress-value", "::-moz-progress-bar",
                   "tabular-nums", ":focus-visible"):
        assert needle in css
    assert ".category-bar" not in css


def test_no_hardcoded_urls_in_profile_and_base_templates():
    for name in ("profile.html", "base.html"):
        text = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert 'href="/' not in text and 'action="/' not in text
