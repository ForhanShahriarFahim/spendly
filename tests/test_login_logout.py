from database.db import get_user_by_id

DEMO = {"email": "demo@spendly.com", "password": "demo123"}


def post_login(client, **overrides):
    return client.post("/login", data={**DEMO, **overrides})


def session_data(client):
    with client.session_transaction() as sess:
        return dict(sess)


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'action="/login"' in response.data


def test_registered_banner(client):
    response = client.get("/login?registered=1")
    assert b"Account created successfully" in response.data


def test_valid_login_redirects_and_sets_session(client):
    response = post_login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    data = session_data(client)
    assert list(data) == ["user_id"]


def test_navbar_after_login(client):
    post_login(client)
    html = client.get("/").data
    assert b"Demo User" in html
    assert b"Sign out" in html
    assert b"Get started" not in html


def test_email_is_trimmed_and_case_insensitive(client):
    response = post_login(client, email="  DEMO@Spendly.com ")
    assert response.status_code == 302
    assert "user_id" in session_data(client)


def test_wrong_password_and_unknown_email_share_error(client):
    wrong = post_login(client, password="nope-nope")
    unknown = post_login(client, email="nobody@example.com")
    for response in (wrong, unknown):
        assert response.status_code == 200
        assert b"Invalid email or password." in response.data
        assert session_data(client) == {}


def test_empty_fields_show_error(client):
    for overrides in ({"email": ""}, {"password": ""}):
        response = post_login(client, **overrides)
        assert response.status_code == 200
        assert b"auth-error" in response.data
        assert session_data(client) == {}


def test_error_keeps_email_and_escapes_it(client):
    response = post_login(client, email='"><script>x', password="bad")
    assert b"<script>x" not in response.data
    assert b"&#34;&gt;&lt;script&gt;x" in response.data
    response = post_login(client, password="bad")
    assert b'value="demo@spendly.com"' in response.data
    assert b'value="bad"' not in response.data


def test_login_while_logged_in_redirects(client):
    post_login(client)
    for response in (client.get("/login"), post_login(client)):
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")


def test_stale_session_is_treated_as_logged_out(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/login")
    assert response.status_code == 200
    assert session_data(client) == {}
    assert b"Sign in" in client.get("/").data


def test_logout_clears_session(client):
    post_login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert session_data(client) == {}
    html = client.get("/").data
    assert b"Sign in" in html and b"Get started" in html


def test_logout_while_logged_out(client):
    response = client.get("/logout")
    assert response.status_code == 302


def test_cookie_has_no_password_or_hash(client):
    response = post_login(client)
    cookie = response.headers.get("Set-Cookie", "")
    assert DEMO["password"] not in cookie
    assert "pbkdf2" not in cookie and "scrypt" not in cookie


def test_secret_key_is_set(app):
    assert app.secret_key


def test_get_user_by_id():
    user = get_user_by_id(1)
    assert user["email"] == "demo@spendly.com"
    assert "password_hash" not in user.keys()
    assert get_user_by_id(9999) is None


def test_register_while_logged_in_redirects(client):
    post_login(client)
    get_response = client.get("/register")
    post_response = client.post("/register", data={
        "name": "X", "email": "x@example.com", "password": "password123"})
    for response in (get_response, post_response):
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
