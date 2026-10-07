from datetime import date, timedelta

import pytest

from database.db import CATEGORIES, create_user, get_db

URL = "/expenses/add"


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def demo_id():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
    finally:
        conn.close()


def new_user_login(client, email="new@example.com"):
    user_id = create_user("New User", email, "password123")
    login(client, email, "password123")
    return user_id


def count_expenses(user_id=None):
    conn = get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        return conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
    finally:
        conn.close()


def latest_expense(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def valid_form(**overrides):
    data = {
        "amount": "25.50",
        "category": "Food",
        "date": "2026-01-15",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- access

def test_get_add_expense_logged_out_redirects_to_login(client):
    response = client.get(URL)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_post_add_expense_logged_out_redirects_and_inserts_nothing(client):
    before = count_expenses()
    response = client.post(URL, data=valid_form())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert count_expenses() == before, "Logged-out POST must not insert"


# ---------------------------------------------------------------- form render

def test_get_form_renders_categories_date_and_cancel(client):
    login(client)
    response = client.get(URL)
    assert response.status_code == 200
    html = response.data.decode()
    for category in CATEGORIES:
        assert category in html, f"Missing category {category}"
    assert len(CATEGORIES) == 7
    assert date.today().isoformat() in html, "Date should default to today"
    assert 'href="/profile"' in html, "Cancel link should go to /profile"
    assert "Cancel" in html


def test_profile_has_add_expense_link(client):
    login(client)
    html = client.get("/profile").data.decode()
    assert 'href="/expenses/add"' in html
    assert "Add Expense" in html or "Add expense" in html


# ---------------------------------------------------------------- happy path

def test_valid_post_redirects_to_profile_and_inserts_row(client):
    user_id = new_user_login(client)
    response = client.post(URL, data=valid_form())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert count_expenses(user_id) == 1
    row = latest_expense(user_id)
    assert row["amount"] == pytest.approx(25.50)
    assert row["category"] == "Food"
    assert row["date"] == "2026-01-15"
    assert row["description"] == "Lunch"


def test_new_expense_shown_on_profile_with_totals_updated(client):
    new_user_login(client)
    client.post(URL, data=valid_form(amount="40", description="Team lunch"))
    html = client.get("/profile").data.decode()
    assert "Team lunch" in html
    assert "40.00" in html, "Total/amount should reflect the new expense"
    assert "Food" in html
    assert "2026-01-15" in html or "Jan" in html


def test_expense_belongs_to_logged_in_user_and_isolated(client):
    uid = new_user_login(client)
    client.post(URL, data=valid_form(description="PrivateNote123"))
    assert count_expenses(uid) == 1
    assert "PrivateNote123" in client.get("/profile").data.decode()

    client.get("/logout")
    login(client)
    html = client.get("/profile").data.decode()
    assert "PrivateNote123" not in html, "Other users must not see the expense"


def test_forged_user_id_form_field_ignored(client):
    uid = new_user_login(client)
    demo = demo_id()
    demo_before = count_expenses(demo)
    client.post(URL, data=valid_form(user_id=str(demo)))
    assert count_expenses(uid) == 1
    assert count_expenses(demo) == demo_before


# ---------------------------------------------------------------- amount

@pytest.mark.parametrize(
    "amount",
    ["", "abc", "0", "-5", "nan", "inf", "-inf", "1e999", "99999999999"],
)
def test_invalid_amount_rerenders_with_error_and_no_insert(client, amount):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(amount=amount))
    assert response.status_code == 200, f"amount={amount!r} should re-render"
    assert b"auth-error" in response.data, "Expected inline error message"
    assert count_expenses(uid) == 0


def test_amount_rounded_to_two_decimals(client):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(amount="12.345"))
    assert response.status_code == 302
    assert latest_expense(uid)["amount"] == pytest.approx(12.35)


def test_amount_that_rounds_to_zero_rejected(client):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(amount="0.001"))
    assert response.status_code == 200
    assert count_expenses(uid) == 0


def test_whitespace_trimmed_amount_accepted(client):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(amount="  15.00  "))
    assert response.status_code == 302
    assert latest_expense(uid)["amount"] == pytest.approx(15.0)


# ---------------------------------------------------------------- category

@pytest.mark.parametrize("category", ["Gambling", "", "food", "<b>x</b>"])
def test_tampered_category_rejected(client, category):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(category=category))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert count_expenses(uid) == 0


def test_missing_category_rejected(client):
    uid = new_user_login(client)
    data = valid_form()
    del data["category"]
    response = client.post(URL, data=data)
    assert response.status_code == 200
    assert count_expenses(uid) == 0


# ---------------------------------------------------------------- date

@pytest.mark.parametrize(
    "bad_date", ["", "not-a-date", "2026-13-01", "2026-02-30", "15/01/2026"]
)
def test_malformed_date_rejected(client, bad_date):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(date=bad_date))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert count_expenses(uid) == 0


def test_missing_date_rejected(client):
    uid = new_user_login(client)
    data = valid_form()
    del data["date"]
    response = client.post(URL, data=data)
    assert response.status_code == 200
    assert count_expenses(uid) == 0


def test_future_date_accepted(client):
    uid = new_user_login(client)
    future = (date.today() + timedelta(days=30)).isoformat()
    response = client.post(URL, data=valid_form(date=future))
    assert response.status_code == 302
    assert latest_expense(uid)["date"] == future


# ---------------------------------------------------------------- description

def test_description_200_chars_accepted(client):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(description="a" * 200))
    assert response.status_code == 302
    assert latest_expense(uid)["description"] == "a" * 200


def test_description_201_chars_rejected(client):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(description="a" * 201))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert count_expenses(uid) == 0


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_description_stored_as_null(client, blank):
    uid = new_user_login(client)
    response = client.post(URL, data=valid_form(description=blank))
    assert response.status_code == 302
    assert latest_expense(uid)["description"] is None


def test_script_description_escaped_on_profile(client):
    new_user_login(client)
    client.post(URL, data=valid_form(description="<script>alert(1)</script>"))
    html = client.get("/profile").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_sql_injection_description_stored_literally(client):
    uid = new_user_login(client)
    payload = "x'); DROP TABLE expenses;--"
    response = client.post(URL, data=valid_form(description=payload))
    assert response.status_code == 302
    assert latest_expense(uid)["description"] == payload


# ---------------------------------------------------------------- sticky values

def test_sticky_values_preserved_after_error(client):
    new_user_login(client)
    response = client.post(
        URL,
        data=valid_form(
            amount="abc", category="Transport", date="2026-03-04",
            description="Sticky note",
        ),
    )
    assert response.status_code == 200
    html = response.data.decode()
    assert "2026-03-04" in html
    assert "Sticky note" in html
    assert "abc" in html
    # Selected category preserved
    assert 'value="Transport" selected' in html or "selected" in html


# ---------------------------------------------------------------- helper

def test_create_expense_helper_returns_int_id(client):
    from database.db import create_expense

    uid = create_user("Helper User", "helper@example.com", "password123")
    new_id = create_expense(uid, 9.99, "Bills", "2026-02-01", "Power")
    assert isinstance(new_id, int)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (new_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["user_id"] == uid
    assert row["category"] == "Bills"
    assert row["amount"] == pytest.approx(9.99)


def test_create_expense_helper_blank_description_is_null(client):
    from database.db import create_expense

    uid = create_user("Helper User", "helper2@example.com", "password123")
    new_id = create_expense(uid, 5, "Other", "2026-02-01", "")
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT description FROM expenses WHERE id = ?", (new_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["description"] is None


# ---------------------------------------------------------------- stubs

def test_delete_stub_unchanged(client):
    response = client.get("/expenses/1/delete")
    assert response.status_code == 200
    assert b"coming in Step 9" in response.data
