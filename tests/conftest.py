import pytest

import database.db
from app import app as flask_app


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    # get_db() reads DB_PATH at call time, so patching the module attribute
    # keeps every test off the real expense_tracker.db.
    monkeypatch.setattr(database.db, "DB_PATH", str(tmp_path / "test.db"))
    database.db.init_db()
    database.db.seed_db()


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    return flask_app
