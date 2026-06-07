import os
import tempfile

import pytest

import database.db as db_module
from app import app as flask_app


@pytest.fixture
def app():
    """Create a Flask app with a temporary test database."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    original_db = db_module.DATABASE
    db_module.DATABASE = db_path

    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        db_module.init_db()

    yield flask_app

    db_module.DATABASE = original_db
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()
