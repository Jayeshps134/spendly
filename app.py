from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

from database.db import (get_db, init_db, seed_db, create_user, get_user_by_email,
                         get_user_by_id, get_expense_stats, get_recent_expenses,
                         get_category_breakdown)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key"


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


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

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

    # ── Summary stats ── #
    stats_raw = get_expense_stats(user_id)
    stats = {
        "total_spent": f"${stats_raw['total_spent']:,.2f}",
        "transaction_count": stats_raw["transaction_count"],
        "top_category": stats_raw["top_category"],
    }

    # ── Transaction history ── #
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

    # ── Category breakdown ── #
    breakdown = get_category_breakdown(user_id)
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
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


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
