"""
Tests for the Add Expense feature.

Feature spec: .claude/specs/07-add-expense.md

Covers:
  - Auth guard (unauthenticated GET/POST redirect to /login)
  - GET /expenses/add renders the form with all expected fields
  - POST /expenses/add with valid data creates an expense and redirects to /profile
  - POST /expenses/add with optional description omitted stores NULL
  - Validation errors: empty/missing amount, amount <= 0, invalid amount string,
    empty/missing category, invalid category, empty/missing date, invalid date format,
    future date
  - Form pre-fills submitted values on validation error
  - DB side effects: expense row inserted with correct values
  - HTTP semantics: correct status codes
  - Edge cases: very large amounts, SQL injection attempts
  - "Add Expense" link appears in navbar for logged-in users
"""

import os
import tempfile

import pytest
from app import app as flask_app
from database.db import init_db


# ── Standard fixtures ── #


@pytest.fixture
def app():
    """Create a Flask app instance with isolated temp-file DB for testing.

    Uses a temporary file-based SQLite database so that multiple calls to
    get_db() share the same database. This is necessary because each call to
    sqlite3.connect(':memory:') creates a new, independent in-memory DB.
    """
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_spendly_")
    os.close(fd)
    import database.db as db_mod
    db_mod.DATABASE = db_path
    with flask_app.app_context():
        init_db()
        yield flask_app
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    """A test client without an active session."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client that is already logged in as a registered user."""
    client.post("/register", data={
        "name": "Test User",
        "email": "test@spendly.com",
        "password": "password123",
    })
    return client


# ── Auth guard tests ── #


class TestAuthGuard:
    """Unauthenticated requests to /expenses/add must redirect to /login."""

    def test_get_add_expense_without_login_redirects(self, client):
        """GET /expenses/add without a session redirects to /login."""
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Expected redirect for unauthenticated GET request"
        )
        assert "/login" in response.headers["Location"], (
            "Expected redirect to /login"
        )

    def test_post_add_expense_without_login_redirects(self, client):
        """POST /expenses/add without a session redirects to /login."""
        response = client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-06-14",
            "description": "Test expense",
        })
        assert response.status_code == 302, (
            "Expected redirect for unauthenticated POST request"
        )
        assert "/login" in response.headers["Location"], (
            "Expected redirect to /login"
        )


# ── GET /expenses/add happy path tests ── #


class TestAddExpenseForm:
    """The add-expense form page renders correctly for logged-in users."""

    def test_get_add_expense_returns_200(self, auth_client):
        """GET /expenses/add while logged in returns 200 OK."""
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, "Expected 200 OK"

    def test_form_contains_amount_field(self, auth_client):
        """The form includes an Amount number input."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert '<input type="number"' in html, "Expected number input for amount"
        assert 'name="amount"' in html, "Expected field named 'amount'"

    def test_form_contains_category_dropdown(self, auth_client):
        """The form includes a Category select dropdown with 7 options."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert '<select' in html, "Expected select element"
        assert 'name="category"' in html, "Expected field named 'category'"

        # Check all 7 fixed categories appear as options
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in categories:
            assert cat in html, f"Expected category '{cat}' in dropdown options"

    def test_form_contains_date_field(self, auth_client):
        """The form includes a Date input."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert '<input type="date"' in html, "Expected date input"
        assert 'name="date"' in html, "Expected field named 'date'"

    def test_form_contains_description_field(self, auth_client):
        """The form includes an optional Description text input."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert 'name="description"' in html, "Expected field named 'description'"
        assert "optional" in html.lower(), "Description should be marked as optional"

    def test_form_contains_submit_button(self, auth_client):
        """The form includes a submit button."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert '<button' in html, "Expected a submit button"
        assert 'type="submit"' in html or "type='submit'" in html, (
            "Expected submit type button"
        )

    def test_form_contains_cancel_link_to_profile(self, auth_client):
        """The form includes a Cancel link that goes to /profile."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert "/profile" in html, "Expected a link to profile page"
        assert "Cancel" in html, "Expected Cancel link text"

    def test_form_uses_post_method(self, auth_client):
        """The form uses POST method to /expenses/add."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert 'method="POST"' in html or "method='POST'" in html, (
            "Expected POST method on the form"
        )
        assert 'action="/expenses/add"' in html or "action='/expenses/add'" in html, (
            "Expected form action to /expenses/add"
        )

    def test_page_title_mentions_add_expense(self, auth_client):
        """The page title or heading mentions Add Expense."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert "Add Expense" in html, "Expected 'Add Expense' title or heading"

    def test_navbar_contains_add_expense_link(self, auth_client):
        """The 'Add Expense' link appears in the nav bar for logged-in users."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        # The nav bar should contain a link to /expenses/add
        assert "/expenses/add" in html, (
            "'Add Expense' link should appear in nav bar for logged-in users"
        )
        assert "Add Expense" in html, (
            "'Add Expense' text should appear in nav bar"
        )


# ── POST /expenses/add happy path tests ── #


class TestAddExpenseSubmitSuccess:
    """Submitting valid data creates an expense and redirects to profile."""

    def test_valid_submission_redirects_to_profile(self, auth_client):
        """Submitting valid form data redirects to /profile."""
        response = auth_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "Food",
            "date": "2026-06-14",
            "description": "Lunch at a cafe",
        })
        assert response.status_code == 302, "Expected 302 redirect on success"
        assert "/profile" in response.headers["Location"], (
            "Expected redirect to /profile"
        )

    def test_valid_submission_inserts_expense_in_db(self, auth_client, app):
        """A valid submission creates a row in the expenses table."""
        # Count expenses before
        import database.db as db_mod
        before = _count_expenses()

        auth_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "Food",
            "date": "2026-06-14",
            "description": "Lunch at a cafe",
        })

        after = _count_expenses()
        assert after == before + 1, (
            f"Expected one new expense, but count went from {before} to {after}"
        )

    def test_valid_submission_stores_correct_values(self, auth_client):
        """The inserted expense row has the correct data."""
        auth_client.post("/expenses/add", data={
            "amount": "99.99",
            "category": "Shopping",
            "date": "2026-06-14",
            "description": "New shoes",
        })

        # Verify the inserted row
        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert row["user_id"] == 1, "Expense should belong to user_id 1"
            assert float(row["amount"]) == pytest.approx(99.99), (
                f"Expected amount 99.99, got {row['amount']}"
            )
            assert row["category"] == "Shopping", (
                f"Expected category 'Shopping', got '{row['category']}'"
            )
            assert row["date"] == "2026-06-14", (
                f"Expected date '2026-06-14', got '{row['date']}'"
            )
            assert row["description"] == "New shoes", (
                f"Expected description 'New shoes', got '{row['description']}'"
            )
        finally:
            conn.close()

    def test_valid_submission_without_description_stores_null(self, auth_client):
        """Omitting the description stores NULL in the database."""
        auth_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Transport",
            "date": "2026-06-14",
            "description": "",  # empty string, should become None/NULL
        })

        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert row["description"] is None, (
                f"Expected NULL description, got '{row['description']}'"
            )
        finally:
            conn.close()

    def test_valid_submission_positive_amount_works(self, auth_client):
        """A valid positive amount (e.g., 0.01) is accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount": "0.01",
            "category": "Other",
            "date": "2026-06-14",
        })
        assert response.status_code == 302, "Expected 302 redirect for valid amount 0.01"
        assert "/profile" in response.headers["Location"]

    def test_valid_submission_large_amount_works(self, auth_client):
        """A very large amount is accepted and stored correctly."""
        response = auth_client.post("/expenses/add", data={
            "amount": "999999.99",
            "category": "Bills",
            "date": "2026-06-14",
            "description": "Large purchase",
        })
        assert response.status_code == 302, "Expected 302 redirect for large amount"
        assert "/profile" in response.headers["Location"]

    def test_all_seven_categories_accepted(self, auth_client):
        """Each of the 7 fixed categories is accepted on submission."""
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for i, cat in enumerate(categories):
            response = auth_client.post("/expenses/add", data={
                "amount": f"{10 + i}.00",
                "category": cat,
                "date": "2026-06-14",
            })
            assert response.status_code == 302, (
                f"Expected 302 for valid category '{cat}', got {response.status_code}"
            )

    def test_expenses_are_isolated_to_correct_user(self, auth_client):
        """An expense created by one user should belong to that user."""
        # auth_client is logged in as user_id=1
        auth_client.post("/expenses/add", data={
            "amount": "55.00",
            "category": "Health",
            "date": "2026-06-14",
            "description": "Isolation test",
        })

        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT user_id FROM expenses ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert row["user_id"] == 1, (
                f"Expense should belong to user 1, got user {row['user_id']}"
            )
        finally:
            conn.close()


# ── Validation error tests ── #


class TestAmountValidation:
    """Validation of the 'amount' field."""

    def test_empty_amount_shows_error(self, auth_client):
        """Submitting with an empty amount shows an error and re-renders the form."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 (re-render form) for empty amount"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "Amount" in html, "Error should mention the amount field"

    def test_missing_amount_shows_error(self, auth_client):
        """Submitting without an amount field at all shows an error."""
        response = auth_client.post("/expenses/add", data={
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 (re-render form) for missing amount"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"

    def test_zero_amount_shows_error(self, auth_client):
        """Submitting with amount = 0 shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 (re-render form) for zero amount"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "greater than zero" in html.lower(), (
            "Error should mention amount must be greater than zero"
        )

    def test_negative_amount_shows_error(self, auth_client):
        """Submitting with a negative amount shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "-15.00",
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 for negative amount"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"

    def test_non_numeric_amount_shows_error(self, auth_client):
        """Submitting with text instead of a number shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "twelve dollars",
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 for non-numeric amount"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "valid number" in html.lower() or "amount" in html.lower(), (
            "Error should mention invalid amount"
        )

    def test_zero_amount_does_not_insert_expense(self, auth_client):
        """Amount = 0 should not create a database entry."""
        before = _count_expenses()

        auth_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-06-14",
        })

        after = _count_expenses()
        assert after == before, (
            f"Expense count should not change after invalid submission "
            f"(was {before}, now {after})"
        )


class TestCategoryValidation:
    """Validation of the 'category' field."""

    def test_empty_category_shows_error(self, auth_client):
        """Submitting with an empty category shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 for empty category"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "Category" in html, "Error should mention category"

    def test_missing_category_shows_error(self, auth_client):
        """Submitting without a category field shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 for missing category"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"

    def test_invalid_category_shows_error(self, auth_client):
        """Submitting a category not in the 7 fixed categories shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "30.00",
            "category": "InvalidCategory",
            "date": "2026-06-14",
        })
        assert response.status_code == 200, "Expected 200 for invalid category"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "Invalid category" in html or "invalid" in html.lower(), (
            "Error should mention invalid category"
        )

    def test_case_mismatched_category_shows_error(self, auth_client):
        """Submitting 'food' instead of 'Food' (case-sensitive) is rejected."""
        response = auth_client.post("/expenses/add", data={
            "amount": "30.00",
            "category": "food",  # lowercase, should fail case-sensitive match
            "date": "2026-06-14",
        })
        # The spec says case-sensitive match — 'food' is not in the 7 categories
        assert response.status_code == 200, "Expected 200 for case-mismatched category"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected error message for case-mismatched category"
        assert "Invalid category" in html or "invalid" in html.lower(), (
            "Error should mention invalid category"
        )

    def test_sql_injection_attempt_in_category_is_safe(self, auth_client):
        """An SQL injection attempt in the category field should not corrupt the DB."""
        before = _count_expenses()

        auth_client.post("/expenses/add", data={
            "amount": "30.00",
            "category": "Food'; DROP TABLE expenses; --",
            "date": "2026-06-14",
        })

        after = _count_expenses()
        # The expenses table should still exist and have the same count
        assert after == before, (
            "SQL injection in category should not create an expense or drop tables"
        )


class TestDateValidation:
    """Validation of the 'date' field."""

    def test_empty_date_shows_error(self, auth_client):
        """Submitting with an empty date shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
            "date": "",
        })
        assert response.status_code == 200, "Expected 200 for empty date"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "Date" in html, "Error should mention date"

    def test_missing_date_shows_error(self, auth_client):
        """Submitting without a date field shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
        })
        assert response.status_code == 200, "Expected 200 for missing date"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"

    def test_invalid_date_format_shows_error(self, auth_client):
        """Submitting a non-YYYY-MM-DD date shows an error."""
        test_dates = [
            "14-06-2026",    # DD-MM-YYYY
            "June 14, 2026",  # human readable
            "not-a-date",    # garbage
            "2026/06/14",    # wrong separator
            "20260614",      # missing dashes
        ]
        for bad_date in test_dates:
            response = auth_client.post("/expenses/add", data={
                "amount": "25.00",
                "category": "Food",
                "date": bad_date,
            })
            assert response.status_code == 200, (
                f"Expected 200 for invalid date '{bad_date}', got {response.status_code}"
            )
            html = response.data.decode()
            assert "error" in html.lower(), (
                f"Expected error message for invalid date '{bad_date}'"
            )

    def test_future_date_shows_error(self, auth_client):
        """Submitting a future date shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Food",
            "date": "2099-12-31",
        })
        assert response.status_code == 200, "Expected 200 for future date"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"
        assert "future" in html.lower(), "Error should mention future date"

    def test_today_date_is_accepted(self, auth_client):
        """Today's date should be accepted (not treated as future)."""
        from datetime import date
        today = date.today().isoformat()

        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
            "date": today,
        })
        assert response.status_code == 302, (
            f"Expected 302 redirect for today's date '{today}', got {response.status_code}"
        )

    def test_past_date_is_accepted(self, auth_client):
        """A past date should be accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
            "date": "2020-01-15",
        })
        assert response.status_code == 302, "Expected 302 redirect for past date"


class TestCombinedValidation:
    """Multiple fields invalid at once."""

    def test_all_fields_empty_shows_errors(self, auth_client):
        """Submitting with all fields empty shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "",
            "date": "",
            "description": "",
        })
        assert response.status_code == 200, "Expected 200 for empty form"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected at least one error message"
        # The form should still be present
        assert "Add Expense" in html, "Form should be re-rendered"

    def test_only_description_provided_shows_error(self, auth_client):
        """Submitting only the optional description without required fields shows an error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "",
            "date": "",
            "description": "Just a note",
        })
        assert response.status_code == 200, "Expected 200 for missing required fields"
        html = response.data.decode()
        assert "error" in html.lower(), "Expected an error message"


# ── Form pre-fill on validation error tests ── #


class TestFormPrefillOnError:
    """When validation fails, the form should pre-fill the submitted values."""

    def test_prefills_amount_on_error(self, auth_client):
        """The amount field retains the submitted value on validation error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "",  # trigger validation error
            "date": "2026-06-14",
        })
        html = response.data.decode()
        assert 'value="42.50"' in html or "value='42.50'" in html or "42.50" in html, (
            "Amount value should be pre-filled on error"
        )

    def test_prefills_category_on_error(self, auth_client):
        """The category dropdown retains the selected value on validation error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",  # trigger validation error
            "category": "Food",
            "date": "2026-06-14",
        })
        html = response.data.decode()
        assert "Food" in html, "Category value should appear in the HTML"
        assert "selected" in html, "A selected attribute should be present"

    def test_prefills_date_on_error(self, auth_client):
        """The date field retains the submitted value on validation error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",  # trigger validation error
            "category": "Food",
            "date": "2026-06-01",
        })
        html = response.data.decode()
        assert "2026-06-01" in html, "Date value should be pre-filled on error"

    def test_prefills_description_on_error(self, auth_client):
        """The description field retains the submitted value on validation error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "",  # trigger validation error
            "category": "Food",
            "date": "2026-06-14",
            "description": "My test description",
        })
        html = response.data.decode()
        assert "My test description" in html, (
            "Description value should be pre-filled on error"
        )

    def test_form_still_shows_after_error(self, auth_client):
        """After a validation error, the full add-expense form is still rendered."""
        response = auth_client.post("/expenses/add", data={
            "amount": "-5",
            "category": "UnknownCategory",
            "date": "bad-date",
        })
        html = response.data.decode()
        assert 'name="amount"' in html, "Amount field should still be present"
        assert 'name="category"' in html, "Category field should still be present"
        assert 'name="date"' in html, "Date field should still be present"
        assert 'name="description"' in html, "Description field should still be present"
        assert '<form' in html, "Form element should still be present"


# ── DB helper function tests ── #


class TestDBCreateExpenseHelper:
    """Direct tests for the create_expense() function in database/db.py."""

    @pytest.fixture
    def db_app(self):
        """App fixture with a user for direct DB helper testing."""
        flask_app.config.update({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        })
        fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_spendly_")
        os.close(fd)
        import database.db as db_mod
        db_mod.DATABASE = db_path
        with flask_app.app_context():
            init_db()
            # Insert a test user
            conn = db_mod.get_db()
            try:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ("DB Test User", "dbtest@spendly.com", "hash"),
                )
                conn.commit()
            finally:
                conn.close()
        yield flask_app
        # Cleanup
        try:
            os.unlink(db_path)
        except OSError:
            pass

    def test_create_expense_returns_id(self, db_app):
        """create_expense returns the new expense's id."""
        from database.db import create_expense

        with db_app.app_context():
            expense_id = create_expense(1, 25.00, "Food", "2026-06-14", "Test")

        assert expense_id is not None, "Expected a non-None expense ID"
        assert isinstance(expense_id, int), f"Expected integer ID, got {type(expense_id)}"
        assert expense_id > 0, f"Expected positive ID, got {expense_id}"

    def test_create_expense_inserts_correct_data(self, db_app):
        """create_expense inserts a row with correct values."""
        from database.db import create_expense

        with db_app.app_context():
            expense_id = create_expense(1, 99.99, "Shopping", "2026-06-14", "New item")

        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            assert row is not None, "Expense row should exist"
            assert row["user_id"] == 1
            assert float(row["amount"]) == pytest.approx(99.99)
            assert row["category"] == "Shopping"
            assert row["date"] == "2026-06-14"
            assert row["description"] == "New item"
        finally:
            conn.close()

    def test_create_expense_without_description_stores_null(self, db_app):
        """create_expense with description=None stores NULL."""
        from database.db import create_expense

        with db_app.app_context():
            expense_id = create_expense(1, 15.00, "Transport", "2026-06-14", None)

        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            assert row["description"] is None, (
                f"Expected NULL, got '{row['description']}'"
            )
        finally:
            conn.close()

    def test_create_expense_negative_amount_raises_value_error(self, db_app):
        """create_expense with negative amount raises ValueError."""
        from database.db import create_expense

        with db_app.app_context():
            with pytest.raises(ValueError, match="positive"):
                create_expense(1, -10.00, "Food", "2026-06-14")

    def test_create_expense_zero_amount_raises_value_error(self, db_app):
        """create_expense with zero amount raises ValueError."""
        from database.db import create_expense

        with db_app.app_context():
            with pytest.raises(ValueError, match="positive"):
                create_expense(1, 0, "Food", "2026-06-14")

    def test_create_expense_empty_category_raises_value_error(self, db_app):
        """create_expense with empty category raises ValueError."""
        from database.db import create_expense

        with db_app.app_context():
            with pytest.raises(ValueError):
                create_expense(1, 25.00, "", "2026-06-14")

    def test_create_expense_empty_date_raises_value_error(self, db_app):
        """create_expense with empty date raises ValueError."""
        from database.db import create_expense

        with db_app.app_context():
            with pytest.raises(ValueError):
                create_expense(1, 25.00, "Food", "")

    def test_create_expense_amount_none_raises_value_error(self, db_app):
        """create_expense with amount=None raises ValueError."""
        from database.db import create_expense

        with db_app.app_context():
            with pytest.raises(ValueError):
                create_expense(1, None, "Food", "2026-06-14")

    def test_create_expense_uses_parameterized_query(self, db_app):
        """create_expense uses parameterized queries (SQL injection is safe)."""
        from database.db import create_expense

        with db_app.app_context():
            # Attempt SQL injection in description — should be stored literally
            exp_id = create_expense(
                1, 30.00, "Food", "2026-06-14",
                "test'); DROP TABLE expenses; --"
            )

        # Verify the injection string is stored as-is, and the table still exists
        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE id = ?", (exp_id,)
            ).fetchone()
            assert "DROP TABLE" in row["description"], (
                "SQL injection string should be stored literally"
            )
            # Verify table still exists by counting
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            assert count > 0, "expenses table should still exist"
        finally:
            conn.close()


# ── Edge case tests ── #


class TestEdgeCases:
    """Boundary and edge case handling."""

    def test_trailing_spaces_in_amount_are_handled(self, auth_client):
        """Amount with leading/trailing spaces should be parsed correctly."""
        response = auth_client.post("/expenses/add", data={
            "amount": "  25.50  ",
            "category": "Food",
            "date": "2026-06-14",
        })
        assert response.status_code == 302, (
            "Expected 302 redirect for amount with whitespace"
        )

    def test_very_long_description_is_accepted(self, auth_client):
        """A very long description string is stored correctly."""
        long_desc = "A" * 1000

        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Other",
            "date": "2026-06-14",
            "description": long_desc,
        })
        assert response.status_code == 302, "Expected 302 for long description"

        # Verify it was stored
        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert row["description"] == long_desc, (
                "Long description should be stored exactly"
            )
        finally:
            conn.close()

    def test_special_characters_in_description(self, auth_client):
        """Special characters in description are stored correctly."""
        special = "<script>alert('xss')</script> & \"quotes\" 'single'"

        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-06-14",
            "description": special,
        })
        assert response.status_code == 302, "Expected 302 for special chars in description"

        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert row["description"] == special, (
                "Special characters should be stored exactly"
            )
        finally:
            conn.close()

    def test_multiple_submissions_create_distinct_expenses(self, auth_client):
        """Each valid submission creates a separate expense row."""
        before = _count_expenses()

        for i in range(3):
            auth_client.post("/expenses/add", data={
                "amount": f"{10 + i}.00",
                "category": "Food",
                "date": "2026-06-14",
                "description": f"Expense #{i + 1}",
            })

        after = _count_expenses()
        assert after == before + 3, (
            f"Expected 3 new expenses, count went from {before} to {after}"
        )

    def test_error_response_includes_form_structure(self, auth_client):
        """Even when there is a validation error, the page extends base.html."""
        response = auth_client.post("/expenses/add", data={
            "amount": "-1",
            "category": "Food",
            "date": "2026-06-14",
        })
        html = response.data.decode()

        # Should still have the base layout elements
        assert "Spendly" in html, "Page should contain Spendly brand"
        assert "Add Expense" in html, "Form title should be visible"

    def test_get_add_expense_includes_today_date_default(self, auth_client):
        """The date field defaults to today's date on first load."""
        from datetime import date
        today = date.today().isoformat()

        response = auth_client.get("/expenses/add")
        html = response.data.decode()

        assert today in html, (
            f"Today's date '{today}' should appear as default in the form"
        )


# ── Integration tests ── #


class TestIntegration:
    """End-to-end integration tests for the add-expense flow."""

    def test_full_flow_add_expense_and_see_on_profile(self, auth_client):
        """Add an expense and then see it on the profile page."""
        # Step 1: Add an expense
        response = auth_client.post("/expenses/add", data={
            "amount": "77.77",
            "category": "Entertainment",
            "date": "2026-06-14",
            "description": "Integration test expense",
        })
        assert response.status_code == 302, "Expected redirect after adding expense"
        assert "/profile" in response.headers["Location"]

        # Step 2: Follow the redirect to profile
        profile_response = auth_client.get("/profile")
        assert profile_response.status_code == 200
        html = profile_response.data.decode()
        assert "Integration test expense" in html, (
            "New expense should appear on the profile page"
        )
        assert "Entertainment" in html, "Category should appear on profile"

    def test_add_expense_profile_shows_updated_total(self, auth_client):
        """The profile page shows the updated total after adding an expense."""
        # First, check current total (there are no seed expenses from auth_client fixture)
        profile_before = auth_client.get("/profile")
        html_before = profile_before.data.decode()

        # Add an expense
        auth_client.post("/expenses/add", data={
            "amount": "150.00",
            "category": "Bills",
            "date": "2026-06-14",
            "description": "Big bill",
        })

        # Check profile again
        profile_after = auth_client.get("/profile")
        html_after = profile_after.data.decode()
        assert "$150.00" in html_after, (
            "Profile should show $150.00 total after adding the expense"
        )


# ── Helper function ── #


def _count_expenses():
    """Return the number of rows in the expenses table."""
    import database.db as db_mod
    conn = db_mod.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS cnt FROM expenses").fetchone()["cnt"]
    finally:
        conn.close()
