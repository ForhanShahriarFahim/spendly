import pytest


@pytest.mark.parametrize(
    "path",
    ["/", "/register", "/login", "/terms", "/privacy"],
)
def test_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"<html" in response.data.lower()


def test_unknown_page_returns_404(client):
    assert client.get("/does-not-exist").status_code == 404
