import pytest
from werkzeug.security import check_password_hash

from database.db import get_db

VALID = {
    "name": "Test User",
    "email": "test@example.com",
    "password": "password123",
}


def post_register(client, **overrides):
    return client.post("/register", data={**VALID, **overrides})


def count_users():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def fetch_user(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_registration_redirects_and_creates_user(client):
    before = count_users()
    response = post_register(client)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert count_users() == before + 1
    assert fetch_user("test@example.com")["name"] == "Test User"


def test_success_message_shown_only_after_registration(client):
    response = client.post("/register", data=VALID, follow_redirects=True)
    assert b"Account created successfully" in response.data
    assert b"Account created successfully" not in client.get("/login").data


def test_password_is_hashed(client):
    post_register(client)
    stored = fetch_user("test@example.com")["password_hash"]
    assert stored != VALID["password"]
    assert check_password_hash(stored, VALID["password"])


def test_email_is_trimmed_and_lowercased(client):
    post_register(client, email="  A@X.com ")
    assert fetch_user("a@x.com") is not None


def test_duplicate_email_is_case_insensitive(client):
    post_register(client, email="A@x.com")
    before = count_users()
    response = post_register(client, email="a@x.com")
    assert response.status_code == 200
    assert b"already exists" in response.data
    assert count_users() == before


def test_existing_seed_email_rejected(client):
    before = count_users()
    response = post_register(client, email="demo@spendly.com")
    assert response.status_code == 200
    assert b"already exists" in response.data
    assert count_users() == before


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_rejected(client, name):
    before = count_users()
    response = post_register(client, name=name)
    assert response.status_code == 200
    assert b"full name" in response.data
    assert count_users() == before


@pytest.mark.parametrize("email, message", [
    ("", b"enter your email"),
    ("   ", b"enter your email"),
    ("no-at-sign", b"valid email"),
])
def test_invalid_email_rejected(client, email, message):
    before = count_users()
    response = post_register(client, email=email)
    assert response.status_code == 200
    assert message in response.data
    assert count_users() == before


def test_password_length_boundary(client):
    before = count_users()
    response = post_register(client, password="1234567")
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    assert count_users() == before

    assert post_register(client, password="12345678").status_code == 302
    assert count_users() == before + 1


def test_error_repopulates_name_and_email_but_not_password(client):
    secret = "S3cretPass!xyz"
    response = post_register(
        client, name="Jane", email="jane@example.com",
        password=secret[:5],
    )
    assert b'value="Jane"' in response.data
    assert b'value="jane@example.com"' in response.data
    assert secret[:5].encode() not in response.data


def test_integrity_error_race_is_handled(client, monkeypatch):
    # Pre-check misses the duplicate, so the INSERT hits the UNIQUE constraint.
    monkeypatch.setattr("app.get_user_by_email", lambda email: None)
    before = count_users()
    response = post_register(client, email="demo@spendly.com")
    assert response.status_code == 200
    assert b"already exists" in response.data
    assert count_users() == before


def test_registration_sets_no_session_cookie(client):
    response = post_register(client)
    assert "Set-Cookie" not in response.headers
