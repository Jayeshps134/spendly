# Spec: Add Expense

## Overview
Replace the bare `"Add expense — coming in Step 7"` stub at `GET /expenses/add` with a full add-expense form that lets logged-in users record new expenses. The form collects an amount, category (from the fixed 7-category list), date, and optional description, then inserts a row into the `expenses` table. This is the first expense-writing feature — users could already *view* their expenses on the profile page, but couldn't *create* them yet.

## Depends on
- Step 01 — Database setup (`expenses` table must exist)
- Step 03 — Login + Logout (add-expense is logged-in-only; uses `session["user_id"]`)
- Step 05 — Profile page backend (established the DB helper pattern in `database/db.py`)

## Routes
- **Modify** `GET /expenses/add` — render the add-expense form — access level: logged-in only
- **Add** `POST /expenses/add` — validate form data, insert a new expense, redirect back to the form (or to profile on success) — access level: logged-in only

## Database changes
No new tables or columns.

New helper function needed in `database/db.py`:
- `create_expense(user_id, amount, category, date, description=None)` — inserts a new expense row and returns its id. Uses parameterized queries. Raises `ValueError` if validation fails (negative amount, empty category, etc.).

## Templates
- **Create:** `templates/add_expense.html` — the add-expense form page extending `base.html`. Form fields:
  - Amount (number input, required, step="0.01", min="0")
  - Category (select dropdown with the 7 fixed categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other)
  - Date (date input, required, default to today)
  - Description (text input, optional)
  - Submit button + Cancel link back to profile
- **Modify:** `templates/base.html` — add an "Add Expense" link to the logged-in navigation bar alongside Analytics and Profile

## Files to change
- `app.py` — implement the GET/POST handler for `/expenses/add`; add `create_expense` to the imports
- `database/db.py` — add `create_expense()` helper function
- `templates/base.html` — add an "Add Expense" nav link for logged-in users

## Files to create
- `templates/add_expense.html` — the add-expense form page
- `static/css/add-expense.css` — page-specific form styles (following the established pattern from `profile.css`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here, but carry-forward rule)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Authentication guard: check `session.get("user_id")` at the top; if absent, `redirect(url_for("login"))`
- Amount must be stored as a positive REAL value; reject amounts ≤ 0 with an error message
- Category must match one of the 7 fixed categories exactly (case-sensitive match)
- Date must be a valid date in YYYY-MM-DD format; reject invalid or future dates with an error message
- On validation error, re-render the form with the submitted values pre-filled and an error message
- On success, insert into the `expenses` table and redirect to `url_for("profile")` (or to `url_for("add_expense")` with a success flash if flash messages are simpler — prefer redirect to profile so the user sees their new expense)
- The description field is optional — store `None` if left blank
- Import `create_expense` at the top of `app.py` alongside existing DB imports
- Write the DB helper as a standalone function in `database/db.py` — no classes
- Never put DB logic in route functions — all queries go in `database/db.py`
- Use `url_for()` for all internal links and redirects — no hardcoded URLs
- The `/expenses/add` route must always render `add_expense.html` or redirect — never return a raw string
- Form styling should match the existing design language (cards, consistent spacing, the same colour palette used in profile.css)

## Definition of done
- [ ] Visiting `GET /expenses/add` while logged in shows a form with Amount, Category (dropdown), Date, and Description fields
- [ ] Visiting `GET /expenses/add` while logged out redirects to `/login`
- [ ] Submitting the form with valid data creates a new expense in the database and redirects to the profile page
- [ ] Submitting the form with an empty amount shows an error and re-renders the form
- [ ] Submitting the form with amount ≤ 0 shows an error and re-renders the form
- [ ] Submitting the form with an invalid category shows an error and re-renders the form
- [ ] Submitting the form with an invalid/future date shows an error and re-renders the form
- [ ] Submitting the form with only required fields (amount, category, date) works and stores description as NULL
- [ ] The "Add Expense" link appears in the nav bar for logged-in users
- [ ] The form pre-fills submitted values on validation error (the user doesn't lose their input)
- [ ] All queries use parameterised SQL with `?` placeholders
- [ ] App starts and runs on port 5001 without errors
- [ ] The demo user can add an expense and see it appear on the profile page
