import pytest

from database.db import get_db
from werkzeug.security import check_password_hash


class TestGetRegister:
    """GET /register — render the registration form."""

    def test_renders_form(self, client):
        response = client.get("/register")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Create your account" in html
        assert 'method="POST"' in html


class TestPostRegisterSuccess:
    """POST /register — successful registration."""

    def test_creates_user_and_redirects(self, client):
        response = client.post("/register", data={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "password123",
        })
        assert response.status_code == 302
        assert response.headers["Location"] == "/"

    def test_sets_session_user_id(self, client):
        response = client.post("/register", data={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "securepass",
        })
        # Session cookie is set on successful registration
        assert "Set-Cookie" in response.headers
        assert "session" in response.headers["Set-Cookie"]

    def test_user_exists_in_database(self, client):
        client.post("/register", data={
            "name": "Carol",
            "email": "carol@example.com",
            "password": "carol1234",
        })

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", ("carol@example.com",)
        ).fetchone()
        db.close()

        assert user is not None
        assert user["name"] == "Carol"

    def test_password_is_hashed(self, client):
        plaintext = "secret7890"
        client.post("/register", data={
            "name": "Dave",
            "email": "dave@example.com",
            "password": plaintext,
        })

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", ("dave@example.com",)
        ).fetchone()
        db.close()

        stored_hash = user["password_hash"]
        assert stored_hash != plaintext
        assert check_password_hash(stored_hash, plaintext)


class TestPostRegisterValidation:
    """POST /register — validation errors."""

    def test_empty_name(self, client):
        response = client.post("/register", data={
            "name": "",
            "email": "test@example.com",
            "password": "password123",
        })
        assert response.status_code == 200
        assert "Full name is required" in response.data.decode()

    def test_missing_email(self, client):
        response = client.post("/register", data={
            "name": "Eve",
            "email": "",
            "password": "password123",
        })
        assert response.status_code == 200
        assert "valid email" in response.data.decode()

    def test_email_without_at_sign(self, client):
        response = client.post("/register", data={
            "name": "Frank",
            "email": "notanemail",
            "password": "password123",
        })
        assert response.status_code == 200
        assert "valid email" in response.data.decode()

    def test_short_password(self, client):
        response = client.post("/register", data={
            "name": "Grace",
            "email": "grace@example.com",
            "password": "short",
        })
        assert response.status_code == 200
        assert "at least 8 characters" in response.data.decode()

    def test_missing_password(self, client):
        response = client.post("/register", data={
            "name": "Heidi",
            "email": "heidi@example.com",
            "password": "",
        })
        assert response.status_code == 200
        assert "at least 8 characters" in response.data.decode()


class TestPostRegisterDuplicate:
    """POST /register — duplicate email handling."""

    def test_duplicate_email(self, client):
        data = {
            "name": "Ivan",
            "email": "ivan@example.com",
            "password": "password123",
        }

        # First registration — should succeed
        response1 = client.post("/register", data=data)
        assert response1.status_code == 302

        # Second registration with same email — should fail
        response2 = client.post("/register", data=data)
        assert response2.status_code == 200
        assert "already exists" in response2.data.decode()
