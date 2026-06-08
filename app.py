from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

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

    # All data is hardcoded — Step 5 will wire up real DB queries
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "January 2026",
    }

    stats = {
        "total_spent": "$280.98",
        "transaction_count": "8",
        "top_category": "Food",
    }

    transactions = [
        {"date": "2026-06-07", "description": "Lunch at work",         "category": "Food",         "amount": "$15.25"},
        {"date": "2026-06-07", "description": "Coffee with friend",    "category": "Other",        "amount": "$8.50"},
        {"date": "2026-06-06", "description": "New headphones",        "category": "Shopping",      "amount": "$79.99"},
        {"date": "2026-06-05", "description": "Movie tickets",         "category": "Entertainment", "amount": "$24.00"},
        {"date": "2026-06-04", "description": "Gym membership",        "category": "Health",        "amount": "$35.00"},
        {"date": "2026-06-03", "description": "Monthly internet bill", "category": "Bills",         "amount": "$59.99"},
        {"date": "2026-06-02", "description": "Uber ride to downtown", "category": "Transport",     "amount": "$12.75"},
        {"date": "2026-06-01", "description": "Grocery shopping",      "category": "Food",          "amount": "$45.50"},
    ]

    categories = [
        {"name": "Food",          "amount": "$60.75", "percentage": 22},
        {"name": "Shopping",      "amount": "$79.99", "percentage": 28},
        {"name": "Bills",         "amount": "$59.99", "percentage": 21},
        {"name": "Health",        "amount": "$35.00", "percentage": 12},
        {"name": "Entertainment", "amount": "$24.00", "percentage": 9},
        {"name": "Transport",     "amount": "$12.75", "percentage": 5},
        {"name": "Other",         "amount": "$8.50",  "percentage": 3},
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
