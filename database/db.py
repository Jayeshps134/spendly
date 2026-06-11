import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = "spendly.db"


def get_db():
    """Open and return a connection to the SQLite database.

    Returns a connection with:
      - row_factory = sqlite3.Row  (dict-like row access)
      - PRAGMA foreign_keys = ON   (enforce FK constraints)
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't already exist.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert demo data if the users table is empty.

    Inserts one demo user (demo@spendly.com / demo123) and
    8 sample expenses spanning all 7 categories.
    Safe to call multiple times — checks for existing data first.
    """
    conn = get_db()
    try:
        # Prevent duplicate seeding
        count = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        if count > 0:
            return

        # Insert demo user
        password_hash = generate_password_hash("demo123")
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = cur.lastrowid

        # Insert 8 sample expenses
        expenses = [
            (user_id, 45.50, "Food",           "2026-06-01", "Grocery shopping at Trader Joe's"),
            (user_id, 12.75, "Transport",       "2026-06-02", "Uber ride to downtown"),
            (user_id, 59.99, "Bills",           "2026-06-03", "Monthly internet bill"),
            (user_id, 35.00, "Health",          "2026-06-04", "Gym membership"),
            (user_id, 24.00, "Entertainment",   "2026-06-05", "Movie tickets"),
            (user_id, 79.99, "Shopping",        "2026-06-06", "New headphones"),
            (user_id, 8.50,  "Other",           "2026-06-07", "Coffee with friend"),
            (user_id, 15.25, "Food",            "2026-06-07", "Lunch at work"),
        ]

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    """Return the user row for the given email, or None if not found."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    """Create a new user and return their id.

    Hashes the password with werkzeug before storing.
    Raises ValueError if the email is already registered.
    """
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("A user with this email already exists.")
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return the user row for the given id, or None if not found."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _build_date_clause(user_id, start_date=None, end_date=None):
    """Build a parameterized date-filter clause for SQL queries.

    Returns (date_clause, params) where date_clause is a string like
    `` AND date >= ? AND date <= ?`` (with leading space) and params
    is [user_id, *dates] with only the non-None date values appended.
    """
    params = [user_id]
    clause = ""
    if start_date:
        clause += " AND date >= ?"
        params.append(start_date)
    if end_date:
        clause += " AND date <= ?"
        params.append(end_date)
    return clause, params


def get_expense_stats(user_id, start_date=None, end_date=None):
    """Return dict with total_spent (float), transaction_count (int), and top_category (str).

    Optionally filter by date range. When start_date or end_date is provided,
    only expenses within that inclusive range are considered.
    """
    conn = get_db()
    try:
        date_clause, params = _build_date_clause(user_id, start_date, end_date)

        # Aggregate stats
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_spent, "
            "       COUNT(*) AS transaction_count "
            "FROM expenses WHERE user_id = ?" + date_clause,
            params,
        ).fetchone()

        total_spent = float(row["total_spent"])
        transaction_count = int(row["transaction_count"])

        # Top category
        top = conn.execute(
            "SELECT category FROM expenses "
            "WHERE user_id = ?" + date_clause + " "
            "GROUP BY category "
            "ORDER BY SUM(amount) DESC "
            "LIMIT 1",
            params,
        ).fetchone()

        top_category = top["category"] if top else "None"

        return {
            "total_spent": total_spent,
            "transaction_count": transaction_count,
            "top_category": top_category,
        }
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=10):
    """Return a list of expense rows ordered by date descending."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, date, description, category, amount "
            "FROM expenses WHERE user_id = ? "
            "ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()


def get_expenses_by_date_range(user_id, start_date=None, end_date=None):
    """Return expense rows within the given date range (inclusive), ordered by date descending.

    Both start_date and end_date are optional. When only one is provided,
    the range is open-ended on the other side.
    Returns rows with id, date, description, category, and amount.
    """
    conn = get_db()
    try:
        date_clause, params = _build_date_clause(user_id, start_date, end_date)
        return conn.execute(
            "SELECT id, date, description, category, amount "
            "FROM expenses WHERE user_id = ?" + date_clause + " "
            "ORDER BY date DESC",
            params,
        ).fetchall()
    finally:
        conn.close()


def get_category_breakdown(user_id, start_date=None, end_date=None):
    """Return a list of dicts with category, total (float), and percentage (int).

    Optionally filter by date range. When start_date or end_date is provided,
    only expenses within that inclusive range are included.
    """
    conn = get_db()
    try:
        date_clause, params = _build_date_clause(user_id, start_date, end_date)

        rows = conn.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ?" + date_clause + " "
            "GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()

        if not rows:
            return []

        grand_total = sum(float(r["total"]) for r in rows)
        breakdown = []
        for r in rows:
            cat_total = float(r["total"])
            percentage = round(cat_total / grand_total * 100)
            breakdown.append({
                "category": r["category"],
                "total": cat_total,
                "percentage": percentage,
            })

        return breakdown
    finally:
        conn.close()
