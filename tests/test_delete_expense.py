import pytest

from database.db import create_expense, create_user, delete_expense, get_db


def login(client, email, password="password123"):
    return client.post("/login", data={"email": email, "password": password})


def new_user_login(client, email="new@example.com"):
    user_id = create_user("New User", email, "password123")
    login(client, email)
    return user_id


def make_expense(user_id, description="Original"):
    return create_expense(user_id, 10.0, "Bills", "2026-02-01", description)


def row_exists(expense_id):
    conn = get_db()
    try:
        return (
            conn.execute(
                "SELECT 1 FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


@pytest.fixture
def owned(client):
    uid = new_user_login(client)
    return uid, make_expense(uid)


# ---------------------------------------------------------------- access


def test_logged_out_get_redirects_to_login(client):
    uid = create_user("U", "u@example.com", "password123")
    eid = make_expense(uid)
    response = client.get(delete_url(eid))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert row_exists(eid)


def test_logged_out_post_redirects_and_deletes_nothing(client):
    uid = create_user("U", "u@example.com", "password123")
    eid = make_expense(uid)
    response = client.post(delete_url(eid))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert row_exists(eid)


# ---------------------------------------------------------------- confirm page


def test_get_shows_confirmation_and_does_not_delete(client, owned):
    _, eid = owned
    response = client.get(delete_url(eid))
    assert response.status_code == 200
    assert b"Original" in response.data
    assert b"10.00" in response.data
    assert b"Bills" in response.data
    assert b"2026-02-01" in response.data
    assert row_exists(eid)


def test_profile_has_delete_link(client, owned):
    _, eid = owned
    response = client.get("/profile")
    assert delete_url(eid).encode() in response.data


# ---------------------------------------------------------------- delete


def test_post_deletes_and_redirects_to_profile(client, owned):
    _, eid = owned
    response = client.post(delete_url(eid))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert not row_exists(eid)


def test_second_post_returns_404(client, owned):
    _, eid = owned
    client.post(delete_url(eid))
    assert client.post(delete_url(eid)).status_code == 404


def test_post_deletes_only_the_target_row(client, owned):
    uid, eid = owned
    other = make_expense(uid, "Keep me")
    client.post(delete_url(eid))
    assert row_exists(other)


# ---------------------------------------------------------------- 404s


def test_missing_id_returns_404(client, owned):
    assert client.get(delete_url(9999)).status_code == 404
    assert client.post(delete_url(9999)).status_code == 404


def test_other_users_expense_returns_404_and_survives(client, owned):
    other_uid = create_user("Other", "other@example.com", "password123")
    other_eid = make_expense(other_uid, "Theirs")
    assert client.get(delete_url(other_eid)).status_code == 404
    assert client.post(delete_url(other_eid)).status_code == 404
    assert row_exists(other_eid)


# ---------------------------------------------------------------- db helper


class TestDeleteExpense:
    def test_returns_true_and_removes_row(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        assert delete_expense(eid, uid) is True
        assert not row_exists(eid)

    def test_missing_id_returns_false(self):
        uid = create_user("U", "u@example.com", "password123")
        assert delete_expense(9999, uid) is False

    def test_wrong_user_returns_false_and_keeps_row(self):
        uid = create_user("U", "u@example.com", "password123")
        other = create_user("O", "o@example.com", "password123")
        eid = make_expense(uid)
        assert delete_expense(eid, other) is False
        assert row_exists(eid)

    def test_injection_in_id_is_not_possible_via_params(self):
        uid = create_user("U", "u@example.com", "password123")
        eid = make_expense(uid)
        assert delete_expense("1 OR 1=1", uid) is False
        assert row_exists(eid)
