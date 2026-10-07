import pytest

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense,
    get_expense_summary,
    update_expense,
)


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


def fetch_row(expense_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
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


def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def make_expense(
    user_id, amount=10.0, category="Bills", date="2026-02-01", description="Original"
):
    return create_expense(user_id, amount, category, date, description)


@pytest.fixture
def owned(client):
    """Logged-in new user with one expense; returns (user_id, expense_id)."""
    uid = new_user_login(client)
    return uid, make_expense(uid)


def snapshot(expense_id):
    row = fetch_row(expense_id)
    return (
        row["amount"],
        row["category"],
        row["date"],
        row["description"],
        row["user_id"],
    )


# ---------------------------------------------------------------- access


def test_get_edit_logged_out_redirects_to_login(client):
    uid = create_user("U", "u@example.com", "password123")
    eid = make_expense(uid)
    response = client.get(edit_url(eid))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_post_edit_logged_out_redirects_and_changes_nothing(client):
    uid = create_user("U", "u@example.com", "password123")
    eid = make_expense(uid)
    before = snapshot(eid)
    response = client.post(edit_url(eid), data=valid_form(amount="99"))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert snapshot(eid) == before, "Logged-out POST must not modify the row"


# ---------------------------------------------------------------- profile link


def test_profile_recent_rows_have_edit_link_each(client):
    uid = new_user_login(client)
    ids = [make_expense(uid, amount=i + 1) for i in range(3)]
    html = client.get("/profile").data.decode()
    assert "Edit" in html
    for eid in ids:
        assert f'href="{edit_url(eid)}"' in html, f"Missing Edit link for {eid}"


def test_profile_demo_rows_link_to_edit(client):
    login(client)
    html = client.get("/profile").data.decode()
    conn = get_db()
    try:
        ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM expenses WHERE user_id = ?", (demo_id(),)
            ).fetchall()
        ]
    finally:
        conn.close()
    assert any(f'href="{edit_url(i)}"' in html for i in ids)


# ---------------------------------------------------------------- prefill


def test_get_edit_prefills_current_values(client):
    uid = new_user_login(client)
    eid = make_expense(uid, 42.5, "Transport", "2026-03-04", "Taxi ride")
    response = client.get(edit_url(eid))
    assert response.status_code == 200
    html = response.data.decode()
    assert "42.5" in html
    assert "2026-03-04" in html
    assert "Taxi ride" in html
    assert "Transport" in html
    for category in CATEGORIES:
        assert category in html
    assert "Save changes" in html
    assert f'action="{edit_url(eid)}"' in html


def test_get_edit_blank_description_shows_empty_field(client):
    uid = new_user_login(client)
    eid = make_expense(uid, description=None)
    response = client.get(edit_url(eid))
    assert response.status_code == 200
    assert b"None" not in response.data, "NULL description must render empty"


def test_cancel_link_returns_to_profile(owned, client):
    _, eid = owned
    html = client.get(edit_url(eid)).data.decode()
    assert "Cancel" in html
    assert 'href="/profile"' in html


# ---------------------------------------------------------------- happy path


def test_valid_post_redirects_to_profile_and_updates_row(owned, client):
    uid, eid = owned
    response = client.post(
        edit_url(eid),
        data=valid_form(
            amount="75.25", category="Health", date="2026-04-10", description="Pharmacy"
        ),
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    row = fetch_row(eid)
    assert row["amount"] == pytest.approx(75.25)
    assert row["category"] == "Health"
    assert row["date"] == "2026-04-10"
    assert row["description"] == "Pharmacy"
    assert row["user_id"] == uid


def test_updated_values_appear_on_profile(owned, client):
    _, eid = owned
    client.post(
        edit_url(eid), data=valid_form(amount="75.25", description="UniqueEditedNote")
    )
    html = client.get("/profile").data.decode()
    assert "UniqueEditedNote" in html
    assert "75.25" in html
    assert "Original" not in html


def test_edit_does_not_create_new_row(owned, client):
    uid, eid = owned
    total_before = count_expenses()
    user_before = count_expenses(uid)
    client.post(edit_url(eid), data=valid_form())
    assert count_expenses() == total_before
    assert count_expenses(uid) == user_before
    assert get_expense_summary(uid)["count"] == 1


def test_edit_updates_total_and_category_breakdown(client):
    uid = new_user_login(client)
    eid = make_expense(uid, 10, "Bills")
    make_expense(uid, 20, "Bills")
    before = {c["category"]: c for c in get_category_breakdown(uid)}
    assert before["Bills"]["count"] == 2

    client.post(edit_url(eid), data=valid_form(amount="100", category="Shopping"))

    after = {c["category"]: c for c in get_category_breakdown(uid)}
    assert after["Bills"]["count"] == 1, "Old category count should drop"
    assert after["Shopping"]["count"] == 1, "New category count should rise"
    assert after["Shopping"]["total"] == pytest.approx(100)
    assert get_expense_summary(uid)["total"] == pytest.approx(120)
    html = client.get("/profile").data.decode()
    assert "120.00" in html, "Profile total should reflect edit"
    assert "Shopping" in html


def test_forged_user_id_form_field_ignored(owned, client):
    uid, eid = owned
    client.post(edit_url(eid), data=valid_form(user_id=str(demo_id())))
    assert fetch_row(eid)["user_id"] == uid


# ---------------------------------------------------------------- 404s


def test_get_nonexistent_expense_returns_404(client):
    new_user_login(client)
    assert client.get(edit_url(999999)).status_code == 404


def test_post_nonexistent_expense_returns_404(client):
    new_user_login(client)
    before = count_expenses()
    assert client.post(edit_url(999999), data=valid_form()).status_code == 404
    assert count_expenses() == before


def test_get_other_users_expense_returns_404(client):
    other = create_user("Other", "other@example.com", "password123")
    eid = make_expense(other, description="SecretOther")
    new_user_login(client)
    response = client.get(edit_url(eid))
    assert response.status_code == 404
    assert b"SecretOther" not in response.data


def test_post_other_users_expense_returns_404_and_unchanged(client):
    other = create_user("Other", "other@example.com", "password123")
    eid = make_expense(other)
    before = snapshot(eid)
    new_user_login(client)
    response = client.post(edit_url(eid), data=valid_form(amount="1"))
    assert response.status_code == 404
    assert snapshot(eid) == before


def test_foreign_and_missing_404_responses_match(client):
    other = create_user("Other", "other@example.com", "password123")
    eid = make_expense(other)
    new_user_login(client)
    foreign = client.get(edit_url(eid))
    missing = client.get(edit_url(999999))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.data == missing.data, "Must not reveal ownership"


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize(
    "amount",
    ["", "abc", "0", "-5", "nan", "inf", "-inf", "1e999", "99999999999"],
)
def test_invalid_amount_shows_error_and_row_unchanged(owned, client, amount):
    _, eid = owned
    before = snapshot(eid)
    response = client.post(edit_url(eid), data=valid_form(amount=amount))
    assert response.status_code == 200, f"amount={amount!r} should re-render"
    assert b"auth-error" in response.data, "Expected inline error"
    assert snapshot(eid) == before


@pytest.mark.parametrize("category", ["Gambling", "", "food", "<b>x</b>"])
def test_tampered_category_rejected(owned, client, category):
    _, eid = owned
    before = snapshot(eid)
    response = client.post(edit_url(eid), data=valid_form(category=category))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert snapshot(eid) == before


def test_missing_category_rejected(owned, client):
    _, eid = owned
    before = snapshot(eid)
    data = valid_form()
    del data["category"]
    response = client.post(edit_url(eid), data=data)
    assert response.status_code == 200
    assert snapshot(eid) == before


@pytest.mark.parametrize(
    "bad_date", ["", "not-a-date", "2026-13-01", "2026-02-30", "15/01/2026"]
)
def test_malformed_date_rejected(owned, client, bad_date):
    _, eid = owned
    before = snapshot(eid)
    response = client.post(edit_url(eid), data=valid_form(date=bad_date))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert snapshot(eid) == before


def test_missing_date_rejected(owned, client):
    _, eid = owned
    before = snapshot(eid)
    data = valid_form()
    del data["date"]
    response = client.post(edit_url(eid), data=data)
    assert response.status_code == 200
    assert snapshot(eid) == before


def test_description_200_chars_accepted(owned, client):
    _, eid = owned
    response = client.post(edit_url(eid), data=valid_form(description="a" * 200))
    assert response.status_code == 302
    assert fetch_row(eid)["description"] == "a" * 200


def test_description_201_chars_rejected(owned, client):
    _, eid = owned
    before = snapshot(eid)
    response = client.post(edit_url(eid), data=valid_form(description="a" * 201))
    assert response.status_code == 200
    assert b"auth-error" in response.data
    assert snapshot(eid) == before


@pytest.mark.parametrize("blank", ["", "   "])
def test_clearing_description_stores_null(owned, client, blank):
    _, eid = owned
    response = client.post(edit_url(eid), data=valid_form(description=blank))
    assert response.status_code == 302
    assert fetch_row(eid)["description"] is None


def test_sticky_values_preserved_after_error(owned, client):
    _, eid = owned
    response = client.post(
        edit_url(eid),
        data=valid_form(
            amount="abc",
            category="Transport",
            date="2026-03-04",
            description="Sticky note",
        ),
    )
    assert response.status_code == 200
    html = response.data.decode()
    assert "abc" in html
    assert "2026-03-04" in html
    assert "Sticky note" in html
    assert "Transport" in html


# ---------------------------------------------------------------- security


def test_script_description_escaped_on_profile(owned, client):
    _, eid = owned
    client.post(edit_url(eid), data=valid_form(description="<script>alert(1)</script>"))
    html = client.get("/profile").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_sql_injection_description_stored_literally(owned, client):
    _, eid = owned
    payload = "x'); DROP TABLE expenses;--"
    response = client.post(edit_url(eid), data=valid_form(description=payload))
    assert response.status_code == 302
    assert fetch_row(eid)["description"] == payload


# ---------------------------------------------------------------- db helpers


class TestGetExpense:
    def test_returns_row_for_owner(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid, 12.5, "Food", "2026-05-05", "Snack")
        row = get_expense(eid, uid)
        assert row is not None
        assert row["id"] == eid
        assert row["amount"] == pytest.approx(12.5)
        assert row["category"] == "Food"
        assert row["date"] == "2026-05-05"
        assert row["description"] == "Snack"

    def test_returns_none_for_other_user(self):
        owner = create_user("A", "a@example.com", "password123")
        other = create_user("B", "b@example.com", "password123")
        eid = make_expense(owner)
        assert get_expense(eid, other) is None

    def test_returns_none_for_missing_id(self):
        uid = create_user("U", "u@example.com", "password123")
        assert get_expense(999999, uid) is None


class TestUpdateExpense:
    def test_updates_owned_row_and_returns_true(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        created_at = fetch_row(eid)["created_at"]
        assert update_expense(eid, uid, 55.0, "Health", "2026-06-06", "New") is True
        row = fetch_row(eid)
        assert row["amount"] == pytest.approx(55.0)
        assert row["category"] == "Health"
        assert row["date"] == "2026-06-06"
        assert row["description"] == "New"
        assert row["user_id"] == uid
        assert row["created_at"] == created_at

    def test_other_user_returns_false_and_row_unchanged(self):
        owner = create_user("A", "a@example.com", "password123")
        other = create_user("B", "b@example.com", "password123")
        eid = make_expense(owner)
        before = snapshot(eid)
        assert update_expense(eid, other, 1.0, "Food", "2026-06-06", "x") is False
        assert snapshot(eid) == before

    def test_missing_id_returns_false(self):
        uid = create_user("U", "u@example.com", "password123")
        assert update_expense(999999, uid, 1.0, "Food", "2026-06-06", "x") is False

    @pytest.mark.parametrize("blank", ["", None])
    def test_blank_description_stored_as_null(self, blank):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        assert update_expense(eid, uid, 5.0, "Food", "2026-06-06", blank) is True
        assert fetch_row(eid)["description"] is None

    def test_does_not_add_rows(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        before = count_expenses()
        update_expense(eid, uid, 5.0, "Food", "2026-06-06", "x")
        assert count_expenses() == before

    def test_injection_in_description_is_literal(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        payload = "'; DROP TABLE expenses;--"
        update_expense(eid, uid, 5.0, "Food", "2026-06-06", payload)
        assert fetch_row(eid)["description"] == payload
