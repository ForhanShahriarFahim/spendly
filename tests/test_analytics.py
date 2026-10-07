import re

import pytest


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def analytics_link_tags(html):
    """Return every opening <a ...> tag whose href is /analytics."""
    tags = re.findall(r"<a\b[^>]*>", html)
    return [t for t in tags if re.search(r'href="/analytics"', t)]


def get_html(client, path):
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} expected 200"
    return response.data.decode()


# ---------------------------------------------------------------- access

def test_analytics_requires_login(client):
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_analytics_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# ---------------------------------------------------------------- content

def test_analytics_logged_in_returns_200(client):
    login(client)
    assert client.get("/analytics").status_code == 200


@pytest.mark.parametrize(
    "text",
    [
        "Advanced Analytics",
        "Coming Soon",
        "We're working on powerful insights and visualizations",
    ],
)
def test_analytics_page_contains_expected_text(client, text):
    login(client)
    html = get_html(client, "/analytics")
    # Tolerate HTML-escaped apostrophes.
    normalized = html.replace("&#39;", "'").replace("&apos;", "'")
    assert text in normalized, f"Expected {text!r} on analytics page"


def test_analytics_links_analytics_stylesheet(client):
    login(client)
    html = get_html(client, "/analytics")
    assert "css/analytics.css" in html, "Expected analytics.css to be linked"


def test_analytics_extends_base_layout(client):
    login(client)
    html = get_html(client, "/analytics")
    assert 'class="navbar"' in html, "Expected base layout navbar"


# ---------------------------------------------------------------- navbar

@pytest.mark.parametrize("path", ["/", "/profile", "/analytics"])
def test_navbar_shows_analytics_link_when_logged_in(client, path):
    login(client)
    html = get_html(client, path)
    tags = analytics_link_tags(html)
    assert tags, f"Expected an Analytics link on {path}"
    assert "nav-analytics" in tags[0], "Expected nav-analytics class"
    assert "Analytics" in html


@pytest.mark.parametrize("path", ["/", "/login", "/register"])
def test_navbar_hides_analytics_link_when_logged_out(client, path):
    html = get_html(client, path)
    assert not analytics_link_tags(html), f"Analytics link shown on {path}"
    assert "nav-analytics" not in html


# ---------------------------------------------------------------- active state

def test_analytics_link_active_on_analytics_page(client):
    login(client)
    tags = analytics_link_tags(get_html(client, "/analytics"))
    assert tags, "Expected Analytics link"
    tag = tags[0]
    assert re.search(r'class="[^"]*\bactive\b[^"]*"', tag), "Expected active class"
    assert 'aria-current="page"' in tag, "Expected aria-current=page"


@pytest.mark.parametrize("path", ["/profile", "/"])
def test_analytics_link_not_active_on_other_pages(client, path):
    login(client)
    tags = analytics_link_tags(get_html(client, path))
    assert tags, f"Expected Analytics link on {path}"
    tag = tags[0]
    assert not re.search(r'\bactive\b', tag), "Unexpected active class"
    assert "aria-current" not in tag, "Unexpected aria-current"


# ---------------------------------------------------------------- existing nav

@pytest.mark.parametrize("path", ["/", "/profile", "/analytics"])
def test_existing_nav_anchors_remain_when_logged_in(client, path):
    login(client)
    html = get_html(client, path)
    assert '<a href="/profile" class="nav-user">' in html
    assert 'class="nav-signout">Sign out</a>' in html
