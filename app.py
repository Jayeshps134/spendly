from datetime import date, datetime

from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

from database.db import (get_db, init_db, seed_db, create_user, get_user_by_email,
                         get_user_by_id, get_expense_stats, get_recent_expenses,
                         get_expenses_by_date_range, get_category_breakdown,
                         create_expense)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key"

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    # POST — process the form
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    # Validate
    if not name:
        return render_template("register.html", error="Full name is required.")
    if not email or "@" not in email:
        return render_template("register.html", error="A valid email address is required.")
    if not password or len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    try:
        user_id = create_user(name, email, password)
    except ValueError as e:
        return render_template("register.html", error=str(e))

    session["user_id"] = user_id
    return redirect(url_for("landing"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # POST — process the form
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    # Validate
    if not email:
        return render_template("login.html", error="Email is required.")
    if not password:
        return render_template("login.html", error="Password is required.")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    return redirect(url_for("landing"))

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _is_valid_date(s):
    """Return True if s is a YYYY-MM-DD date string."""
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # ── Parse optional date filter ── #
    raw_start = request.args.get("start_date", "").strip()
    raw_end = request.args.get("end_date", "").strip()

    # Validate date format — discard malformed values
    if raw_start and not _is_valid_date(raw_start):
        raw_start = ""
    if raw_end and not _is_valid_date(raw_end):
        raw_end = ""

    # If both provided and start > end, treat as no filter
    if raw_start and raw_end and raw_start > raw_end:
        raw_start = raw_end = ""

    # Convert to None for DB helpers (None = no filter)
    start_date = raw_start or None
    end_date = raw_end or None

    # ── User info ── #
    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    created_dt = datetime.strptime(user_row["created_at"], "%Y-%m-%d %H:%M:%S")
    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "member_since": created_dt.strftime("%B %Y"),
    }

    # ── Summary stats (with optional date filter) ── #
    stats_raw = get_expense_stats(user_id, start_date, end_date)
    stats = {
        "total_spent": f"${stats_raw['total_spent']:,.2f}",
        "transaction_count": stats_raw["transaction_count"],
        "top_category": stats_raw["top_category"],
    }

    # ── Transaction history (filtered or unfiltered) ── #
    if start_date or end_date:
        expense_rows = get_expenses_by_date_range(user_id, start_date, end_date)
    else:
        expense_rows = get_recent_expenses(user_id)

    transactions = [
        {
            "date": r["date"],
            "description": r["description"] or "",
            "category": r["category"],
            "amount": f"${r['amount']:,.2f}",
        }
        for r in expense_rows
    ]

    # ── Category breakdown (with optional date filter) ── #
    breakdown = get_category_breakdown(user_id, start_date, end_date)
    categories = [
        {
            "name": c["category"],
            "amount": f"${c['total']:,.2f}",
            "percentage": c["percentage"],
        }
        for c in breakdown
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return _render_add_expense_form()

    # POST — process the form
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date_str = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip() or None

    # ── Validate amount ── #
    if not amount_raw:
        return _render_add_expense_form(error="Amount is required.")
    try:
        amount = float(amount_raw)
    except ValueError:
        return _render_add_expense_form(error="Amount must be a valid number.")
    if amount <= 0:
        return _render_add_expense_form(error="Amount must be greater than zero.")

    # ── Validate category ── #
    if not category:
        return _render_add_expense_form(error="Category is required.")
    if category not in CATEGORIES:
        return _render_add_expense_form(error="Invalid category selected.")

    # ── Validate date ── #
    if not date_str:
        return _render_add_expense_form(error="Date is required.")
    if not _is_valid_date(date_str):
        return _render_add_expense_form(error="Date must be a valid YYYY-MM-DD format.")
    if date_str > date.today().isoformat():
        return _render_add_expense_form(error="Date cannot be in the future.")

    # ── Insert ── #
    user_id = session["user_id"]
    create_expense(user_id, amount, category, date_str, description)
    return redirect(url_for("profile"))


def _render_add_expense_form(error=None):
    """Render the add-expense form with standard template context."""
    return render_template("add_expense.html",
                           error=error,
                           categories=CATEGORIES,
                           today=date.today().isoformat())


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# ------------------------------------------------------------------ #
# Database initialization                                              #
# ------------------------------------------------------------------ #

with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
