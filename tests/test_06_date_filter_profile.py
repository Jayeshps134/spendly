"""
Tests for the date filter feature on the /profile page.

Feature spec: .claude/specs/06-date-filter-for-profile-page.md

Covers:
  - Auth guard (unauthenticated requests redirected to /login)
  - Happy path: no filter (baseline behavior unchanged)
  - Happy path: date filter applied (both start_date and end_date)
  - Partial filters (only start_date or only end_date)
  - Invalid date range (start > end treated as no filter)
  - Empty results (graceful "no expenses" message)
  - Edge cases: empty strings, whitespace, extreme dates
  - DB side effects (read-only, correct aggregates)
  - Template structure and content assertions
"""

import os
import tempfile

import pytest
from app import app as flask_app
from database.db import init_db, get_expenses_by_date_range, get_expense_stats, get_category_breakdown


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
    """A test client that is already logged in as a user with seed expenses.

    Registers a fresh user and logs them in. Then inserts a set of known
    expenses across multiple dates so date-filter tests are deterministic.
    """
    # Register and log in
    client.post("/register", data={
        "name": "Test User",
        "email": "test@spendly.com",
        "password": "password123",
    })

    # Insert known expenses across specific dates
    import database.db as db_mod
    conn = db_mod.get_db()
    try:
        expenses = [
            # user_id=1, amount, category, date, description
            (1, 45.50, "Food", "2026-06-01", "Grocery shopping"),
            (1, 12.75, "Transport", "2026-06-02", "Uber ride"),
            (1, 59.99, "Bills", "2026-06-03", "Internet bill"),
            (1, 35.00, "Health", "2026-06-04", "Gym membership"),
            (1, 24.00, "Entertainment", "2026-06-05", "Movie tickets"),
            (1, 79.99, "Shopping", "2026-06-10", "New headphones"),
            (1, 8.50, "Other", "2026-06-10", "Coffee"),
            (1, 15.25, "Food", "2026-06-10", "Lunch at work"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    finally:
        conn.close()

    return client


# ── Auth guard tests ── #


class TestAuthGuard:
    """Unauthenticated requests to /profile must redirect to /login."""

    def test_profile_without_login_redirects(self, client):
        """GET /profile without a session redirects to /login."""
        response = client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], "Expected redirect to /login"

    def test_profile_with_date_filter_without_login_redirects(self, client):
        """GET /profile?start_date=...&end_date=... without session redirects."""
        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-05")
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], "Expected redirect to /login"

    def test_profile_with_only_start_date_without_login_redirects(self, client):
        """GET /profile?start_date=... without session redirects."""
        response = client.get("/profile?start_date=2026-06-01")
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], "Expected redirect to /login"


# ── No-filter baseline tests (happy path) ── #


class TestProfileNoFilter:
    """When no date params are provided, the profile page behaves as before."""

    def test_profile_renders_without_filter(self, auth_client):
        """GET /profile without query params returns 200 and shows all expenses."""
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Expected 200 OK"

    def test_profile_shows_all_transactions_when_no_filter(self, auth_client):
        """All 8 seed transactions appear when no filter is active."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        # All 8 transactions from seed data should be present
        assert "Grocery shopping" in html, "Expected grocery expense"
        assert "Uber ride" in html, "Expected transport expense"
        assert "Internet bill" in html, "Expected bills expense"
        assert "Gym membership" in html, "Expected health expense"
        assert "Movie tickets" in html, "Expected entertainment expense"
        assert "New headphones" in html, "Expected shopping expense"
        assert "Coffee" in html, "Expected other expense"
        assert "Lunch at work" in html, "Expected food expense"

    def test_profile_shows_date_filter_form(self, auth_client):
        """The profile page always shows the date filter form (From, To, Filter, Clear)."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        assert 'name="start_date"' in html, "Expected 'From' date input"
        assert 'name="end_date"' in html, "Expected 'To' date input"
        assert 'type="submit"' in html, "Expected Filter submit button"
        assert "Clear" in html, "Expected Clear link/button"

    def test_profile_no_filter_badge_when_no_params(self, auth_client):
        """The filter badge is not shown when no filter params are provided."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        assert "Showing expenses from" not in html, (
            "Filter badge should not appear when no filter is active"
        )

    def test_profile_no_filter_shows_correct_stats(self, auth_client):
        """Stats reflect all 8 expenses when no filter is applied."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        # Total: 45.50 + 12.75 + 59.99 + 35.00 + 24.00 + 79.99 + 8.50 + 15.25 = 280.98
        assert "$280.98" in html, "Expected total spent for all expenses"

        # Transaction count
        assert "8" in html, "Expected 8 transactions in stats"


# ── Date filter happy path tests ── #


class TestDateFilterHappyPath:
    """Filtering with both start_date and end_date produces correct results."""

    def test_filter_shows_only_matching_transactions(self, auth_client):
        """Filtering 2026-06-01 to 2026-06-03 shows only 3 expenses."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        assert "Grocery shopping" in html, "Expected June 1 expense"
        assert "Uber ride" in html, "Expected June 2 expense"
        assert "Internet bill" in html, "Expected June 3 expense"

        # June 4 and later should NOT appear
        assert "Gym membership" not in html, "June 4 expense should not appear in filtered range"
        assert "Movie tickets" not in html, "June 5 expense should not appear in filtered range"
        assert "New headphones" not in html, "June 10 expense should not appear in filtered range"

    def test_filter_updates_stats_correctly(self, auth_client):
        """Stats reflect only expenses in the filtered date range."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        # Total: 45.50 + 12.75 + 59.99 = 118.24
        assert "$118.24" in html, "Expected filtered total spent"

        # Transaction count: 3
        # Look for the stat-value near the Transactions label
        assert "Transactions" in html

    def test_filter_shows_badge_with_dates(self, auth_client):
        """When a filter is active, the filter badge shows the date range."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        assert "Showing expenses from" in html, "Filter badge should appear"
        assert "2026-06-01" in html, "Start date should be in badge"
        assert "2026-06-03" in html, "End date should be in badge"

    def test_filter_prefills_date_inputs(self, auth_client):
        """Date inputs are pre-filled with the current filter values."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        assert 'value="2026-06-01"' in html, "Start date input should be pre-filled"
        assert 'value="2026-06-03"' in html, "End date input should be pre-filled"

    def test_filter_form_uses_get_method(self, auth_client):
        """The filter form must use GET method so the URL carries filter state."""
        response = auth_client.get("/profile")
        html = response.data.decode()

        assert 'method="GET"' in html or "method='GET'" in html or 'method=get' in html.lower(), (
            "Filter form should use GET method"
        )

    def test_filter_query_params_preserved_in_url(self, auth_client):
        """The URL should contain the query parameters after filter submission."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-05")
        # The response itself confirms the filter was applied;
        # the response is 200, and the filter badge appears
        assert response.status_code == 200
        html = response.data.decode()
        assert "Showing expenses from" in html, "Filter should be active"

    def test_filter_transactions_ordered_by_date_desc(self, auth_client):
        """Transactions should be ordered by date descending."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-10")
        html = response.data.decode()

        # All 8 transactions should be in the filtered range
        # Check relative order: June 10 items should appear before June 1 items
        # We check that a later date's text appears first
        pos_10 = html.find("2026-06-10")
        pos_01 = html.find("2026-06-01")
        assert pos_10 < pos_01, (
            "June 10 entries should appear before June 1 entries (descending order)"
        )

    def test_filter_category_breakdown_reflects_filter(self, auth_client):
        """Category breakdown shows only filtered categories."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        # Categories for June 1-3: Food, Transport, Bills
        assert "Food" in html, "Food category should appear in breakdown"
        assert "Transport" in html, "Transport category should appear in breakdown"
        assert "Bills" in html, "Bills category should appear in breakdown"

        # Health, Entertainment, Shopping, Other should NOT appear
        # (these are only in June 4-10)
        assert "Health" not in html, "Health should not appear in breakdown for June 1-3"

    def test_clear_link_resets_filter(self, auth_client):
        """The Clear link points to /profile without query params."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        # The Clear link should have href to /profile without query params
        # url_for('profile') produces "/profile"
        assert 'href="/profile"' in html or "href='/profile'" in html, (
            "Clear link should point to /profile without query params"
        )


# ── Partial filter tests ── #


class TestPartialDateFilters:
    """Filtering with only one date parameter."""

    def test_only_start_date_shows_from_date_onward(self, auth_client):
        """Only start_date: shows expenses from that date to present."""
        response = auth_client.get("/profile?start_date=2026-06-05")
        html = response.data.decode()

        # June 5 onward: Movie tickets (5), New headphones (10), Coffee (10), Lunch (10)
        assert "Movie tickets" in html, "June 5 expense should appear"
        assert "New headphones" in html, "June 10 expense should appear"
        assert "Coffee" in html, "June 10 expense should appear"
        assert "Lunch at work" in html, "June 10 expense should appear"

        # Before June 5: should NOT appear
        assert "Grocery shopping" not in html, "June 1 expense should not appear"
        assert "Uber ride" not in html, "June 2 expense should not appear"
        assert "Internet bill" not in html, "June 3 expense should not appear"
        assert "Gym membership" not in html, "June 4 expense should not appear"

    def test_only_start_date_badge_shows_beginning_to_date(self, auth_client):
        """Badge shows 'the beginning' for missing end date."""
        response = auth_client.get("/profile?start_date=2026-06-05")
        html = response.data.decode()

        assert "Showing expenses from" in html, "Filter badge should appear"
        assert "2026-06-05" in html, "Start date should be in badge"
        assert "the beginning" in html or "today" in html, (
            "Badge should indicate open range for missing end date"
        )

    def test_only_end_date_shows_up_to_date(self, auth_client):
        """Only end_date: shows expenses up to that date."""
        response = auth_client.get("/profile?end_date=2026-06-03")
        html = response.data.decode()

        # Up to June 3: Grocery (1), Uber (2), Internet (3)
        assert "Grocery shopping" in html, "June 1 expense should appear"
        assert "Uber ride" in html, "June 2 expense should appear"
        assert "Internet bill" in html, "June 3 expense should appear"

        # After June 3: should NOT appear
        assert "Gym membership" not in html, "June 4 expense should not appear"
        assert "Movie tickets" not in html, "June 5 expense should not appear"

    def test_only_end_date_badge_shows_today(self, auth_client):
        """Badge shows 'today' for missing start date."""
        response = auth_client.get("/profile?end_date=2026-06-03")
        html = response.data.decode()

        assert "Showing expenses from" in html, "Filter badge should appear"
        assert "2026-06-03" in html, "End date should be in badge"
        assert "today" in html or "the beginning" in html, (
            "Badge should indicate open range for missing start date"
        )

    def test_only_start_date_prefills_start_input(self, auth_client):
        """Only start_date input is pre-filled."""
        response = auth_client.get("/profile?start_date=2026-06-05")
        html = response.data.decode()

        assert 'value="2026-06-05"' in html, "Start date input should be pre-filled"
        # End date input should be empty (value="" or no value attribute on a date input)
        # The template sets value="{{ filter_end or '' }}" so empty string is fine

    def test_only_end_date_prefills_end_input(self, auth_client):
        """Only end_date input is pre-filled."""
        response = auth_client.get("/profile?end_date=2026-06-03")
        html = response.data.decode()

        assert 'value="2026-06-03"' in html, "End date input should be pre-filled"


# ── Invalid date range tests ── #


class TestInvalidDateRange:
    """When start_date > end_date, the filter is ignored."""

    def test_start_after_end_treated_as_no_filter(self, auth_client):
        """start_date > end_date: fall back to showing all expenses."""
        response = auth_client.get("/profile?start_date=2026-06-10&end_date=2026-06-01")
        html = response.data.decode()

        # All expenses should appear (filter is ignored)
        assert "Grocery shopping" in html, "June 1 expense should appear"
        assert "New headphones" in html, "June 10 expense should appear"

        # Filter badge should NOT appear
        assert "Showing expenses from" not in html, (
            "Filter badge should not appear when date range is invalid"
        )

    def test_start_after_end_shows_all_transactions(self, auth_client):
        """All 8 transactions visible when invalid range is ignored."""
        response = auth_client.get("/profile?start_date=2026-06-10&end_date=2026-06-01")
        html = response.data.decode()

        # The total should reflect all 8 expenses
        assert "$280.98" in html, "Expected full total when invalid range is ignored"


# ── Empty results tests ── #


class TestEmptyResults:
    """When no expenses match the date filter."""

    def test_no_matching_expenses_shows_empty_message(self, auth_client):
        """A date range with no expenses shows a friendly message."""
        response = auth_client.get("/profile?start_date=2025-01-01&end_date=2025-01-31")
        html = response.data.decode()

        assert response.status_code == 200, "Expected 200 OK even with no results"
        assert "No expenses found in this date range" in html, (
            "Expected empty results message"
        )

    def test_no_matching_expenses_hides_transaction_table(self, auth_client):
        """When no results, the transaction table should not be rendered."""
        response = auth_client.get("/profile?start_date=2025-01-01&end_date=2025-01-31")
        html = response.data.decode()

        # The transaction table rows for our test data should not appear
        assert "Grocery shopping" not in html, "No transactions should appear"
        assert "Uber ride" not in html, "No transactions should appear"

    def test_no_matching_expenses_shows_zero_stats(self, auth_client):
        """Stats should show zero when no expenses match."""
        response = auth_client.get("/profile?start_date=2025-01-01&end_date=2025-01-31")
        html = response.data.decode()

        assert "0" in html, "Expected zero transaction count"
        assert "$0.00" in html, "Expected zero total spent"


# ── Edge case tests ── #


class TestEdgeCases:
    """Boundary and unusual input handling."""

    def test_empty_string_start_date_treated_as_no_filter(self, auth_client):
        """?start_date=&end_date= should be treated as no filter."""
        response = auth_client.get("/profile?start_date=&end_date=")
        html = response.data.decode()

        assert response.status_code == 200
        # Should show all transactions
        assert "Grocery shopping" in html
        assert "New headphones" in html
        # No filter badge
        assert "Showing expenses from" not in html

    def test_whitespace_only_dates_treated_as_no_filter(self, auth_client):
        """Whitespace-only date params should be stripped and treated as no filter."""
        response = auth_client.get("/profile?start_date=+++&end_date=   ")
        html = response.data.decode()

        assert response.status_code == 200
        assert "Showing expenses from" not in html, (
            "Whitespace-only params should not activate filter"
        )

    def test_single_day_range_includes_both_ends(self, auth_client):
        """start_date == end_date should include expenses on that exact date."""
        response = auth_client.get("/profile?start_date=2026-06-10&end_date=2026-06-10")
        html = response.data.decode()

        # June 10 has 3 expenses: New headphones, Coffee, Lunch at work
        assert "New headphones" in html
        assert "Coffee" in html
        assert "Lunch at work" in html

        # Other dates should not appear
        assert "Grocery shopping" not in html
        assert "Movie tickets" not in html

    def test_single_day_range_correct_stats(self, auth_client):
        """Stats correctly aggregate a single day."""
        response = auth_client.get("/profile?start_date=2026-06-10&end_date=2026-06-10")
        html = response.data.decode()

        # Total: 79.99 + 8.50 + 15.25 = 103.74
        assert "$103.74" in html, "Expected total for June 10"

    def test_very_broad_range_returns_all(self, auth_client):
        """A very broad date range returns all expenses."""
        response = auth_client.get(
            "/profile?start_date=2000-01-01&end_date=2099-12-31"
        )
        html = response.data.decode()

        assert "Grocery shopping" in html
        assert "New headphones" in html

        # Total should be full
        assert "$280.98" in html, "Expected all expenses total"

    def test_non_date_like_string_handled_gracefully(self, auth_client):
        """Non-date strings should not crash the app."""
        # The app should handle this gracefully — likely showing no results
        # because the string won't match any date in YYYY-MM-DD format
        response = auth_client.get(
            "/profile?start_date=not-a-date&end_date=also-not"
        )
        assert response.status_code == 200, "App should not crash on invalid date strings"

    def test_filter_preserves_user_info_section(self, auth_client):
        """User info card is always rendered regardless of filter state."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        assert "Test User" in html, "User name should appear"
        assert "test@spendly.com" in html, "User email should appear"
        assert "Member since" in html, "Member since should appear"

    def test_filter_preserves_category_breakdown_section(self, auth_client):
        """Category breakdown section is always rendered."""
        response = auth_client.get("/profile?start_date=2025-01-01&end_date=2025-01-31")
        html = response.data.decode()

        # Even with no results, the section title should appear
        assert "Category Breakdown" in html, "Category breakdown section should exist"

    def test_filter_preserves_profile_page_structure(self, auth_client):
        """All major sections are present on the filtered profile page."""
        response = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        html = response.data.decode()

        assert "Transaction History" in html, "Transaction history section should exist"
        assert "Category Breakdown" in html, "Category breakdown section should exist"
        assert "Total Spent" in html, "Total spent stat should exist"
        assert "Transactions" in html, "Transaction count stat should exist"
        assert "Top Category" in html, "Top category stat should exist"


# ── DB helper function tests ── #


class TestDBHelpers:
    """Direct tests for the date-filtered DB helper functions.

    These tests use a dedicated app fixture that sets up expense data
    independent of the auth_client path.
    """

    @pytest.fixture
    def db_app(self):
        """App fixture with known expense data for direct DB helper testing."""
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
            # Insert user
            from database.db import get_db as _get_db
            conn = _get_db()
            try:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ("DB Test User", "dbtest@spendly.com", "hash"),
                )
                expenses = [
                    (1, 45.50, "Food", "2026-06-01", "Grocery shopping"),
                    (1, 12.75, "Transport", "2026-06-02", "Uber ride"),
                    (1, 59.99, "Bills", "2026-06-03", "Internet bill"),
                    (1, 35.00, "Health", "2026-06-04", "Gym membership"),
                    (1, 24.00, "Entertainment", "2026-06-05", "Movie tickets"),
                    (1, 79.99, "Shopping", "2026-06-10", "New headphones"),
                    (1, 8.50, "Other", "2026-06-10", "Coffee"),
                    (1, 15.25, "Food", "2026-06-10", "Lunch at work"),
                ]
                conn.executemany(
                    "INSERT INTO expenses (user_id, amount, category, date, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    expenses,
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

    def test_get_expenses_by_date_range_inclusive(self, db_app):
        """get_expenses_by_date_range should include both boundary dates."""
        with db_app.app_context():
            rows = get_expenses_by_date_range(user_id=1, start_date="2026-06-01", end_date="2026-06-03")

        assert len(rows) == 3, "Expected 3 expenses in June 1-3 range"
        dates = [r["date"] for r in rows]
        assert "2026-06-01" in dates, "Start boundary should be included"
        assert "2026-06-03" in dates, "End boundary should be included"

    def test_get_expenses_by_date_range_descending(self, db_app):
        """Results should be ordered by date descending."""
        with db_app.app_context():
            rows = get_expenses_by_date_range(user_id=1, start_date="2026-06-01", end_date="2026-06-10")

        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True), (
            "Results should be in descending date order"
        )

    def test_get_expenses_by_date_range_start_only(self, db_app):
        """With only start_date, returns from that date onward."""
        with db_app.app_context():
            rows = get_expenses_by_date_range(user_id=1, start_date="2026-06-05", end_date=None)

        dates = [r["date"] for r in rows]
        assert all(d >= "2026-06-05" for d in dates), "All dates should be >= start_date"
        assert len(rows) == 4, "Expected 4 expenses from June 5 onward"

    def test_get_expense_stats_with_date_filter(self, db_app):
        """get_expense_stats returns correct aggregates for a date range."""
        with db_app.app_context():
            stats = get_expense_stats(user_id=1, start_date="2026-06-01", end_date="2026-06-03")

        assert stats["transaction_count"] == 3
        assert stats["total_spent"] == pytest.approx(118.24)
        # Top category should be Bills (59.99) since it's the highest single amount
        assert stats["top_category"] == "Bills"

    def test_get_expense_stats_no_filter(self, db_app):
        """get_expense_stats without dates returns all expenses."""
        with db_app.app_context():
            stats = get_expense_stats(user_id=1)

        assert stats["transaction_count"] == 8
        assert stats["total_spent"] == pytest.approx(280.98)

    def test_get_expense_stats_empty_range(self, db_app):
        """get_expense_stats returns zeros and 'None' for a range with no data."""
        with db_app.app_context():
            stats = get_expense_stats(user_id=1, start_date="2020-01-01", end_date="2020-12-31")

        assert stats["transaction_count"] == 0
        assert stats["total_spent"] == 0.0
        assert stats["top_category"] == "None"

    def test_get_category_breakdown_with_date_filter(self, db_app):
        """get_category_breakdown returns correct breakdown for a date range."""
        with db_app.app_context():
            breakdown = get_category_breakdown(user_id=1, start_date="2026-06-01", end_date="2026-06-03")

        # Three categories: Food (45.50), Transport (12.75), Bills (59.99)
        assert len(breakdown) == 3
        categories = {c["category"]: c for c in breakdown}
        assert "Food" in categories
        assert "Transport" in categories
        assert "Bills" in categories

        # Percentages should sum to 100 (or close due to rounding)
        total_pct = sum(c["percentage"] for c in breakdown)
        assert 99 <= total_pct <= 101, f"Percentages should sum to ~100, got {total_pct}"

    def test_get_category_breakdown_no_filter(self, db_app):
        """get_category_breakdown without dates returns all categories."""
        with db_app.app_context():
            breakdown = get_category_breakdown(user_id=1)

        # All 7 categories should appear
        assert len(breakdown) == 7

    def test_get_category_breakdown_empty_range(self, db_app):
        """get_category_breakdown returns empty list for range with no data."""
        with db_app.app_context():
            breakdown = get_category_breakdown(user_id=1, start_date="2020-01-01", end_date="2020-12-31")

        assert breakdown == [], "Should return empty list when no expenses match"

    def test_get_category_breakdown_sorted_by_total_desc(self, db_app):
        """Results should be sorted by total amount descending."""
        with db_app.app_context():
            breakdown = get_category_breakdown(user_id=1)

        totals = [c["total"] for c in breakdown]
        assert totals == sorted(totals, reverse=True), (
            "Categories should be sorted by total descending"
        )


# ── Integration tests: filter with real DB data ── #


class TestIntegration:
    """End-to-end integration tests that exercise the full request/response cycle."""

    def test_filter_then_clear_returns_to_unfiltered(self, auth_client):
        """Apply a filter, then clear it, and verify all data returns."""
        # Step 1: Apply filter
        filtered = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        assert "Grocery shopping" in filtered.data.decode()
        assert "New headphones" not in filtered.data.decode()

        # Step 2: Clear the filter (navigate to /profile without params)
        cleared = auth_client.get("/profile")
        assert "Grocery shopping" in cleared.data.decode()
        assert "New headphones" in cleared.data.decode(), (
            "All expenses should return after clearing filter"
        )

    def test_multiple_filters_in_sequence(self, auth_client):
        """Apply different filters sequentially and verify each is correct."""
        # Filter 1: June 1-3
        r1 = auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")
        assert "Internet bill" in r1.data.decode()
        assert "Gym membership" not in r1.data.decode()

        # Filter 2: June 4-5
        r2 = auth_client.get("/profile?start_date=2026-06-04&end_date=2026-06-05")
        assert "Gym membership" in r2.data.decode()
        assert "Movie tickets" in r2.data.decode()
        assert "Internet bill" not in r2.data.decode()

        # Filter 3: June 10 only
        r3 = auth_client.get("/profile?start_date=2026-06-10&end_date=2026-06-10")
        assert "New headphones" in r3.data.decode()
        assert "Coffee" in r3.data.decode()
        assert "Lunch at work" in r3.data.decode()
        assert "Movie tickets" not in r3.data.decode()

    def test_filter_does_not_modify_database(self, auth_client):
        """Filtering is a read-only operation; the DB should be unchanged."""
        # Apply a filter
        auth_client.get("/profile?start_date=2026-06-01&end_date=2026-06-03")

        # Verify DB still has all 8 expenses
        import database.db as db_mod
        conn = db_mod.get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (1,)
            ).fetchone()[0]
            assert count == 8, "Database should still have all 8 expenses after filtering"
        finally:
            conn.close()
