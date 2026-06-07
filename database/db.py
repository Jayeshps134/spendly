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
