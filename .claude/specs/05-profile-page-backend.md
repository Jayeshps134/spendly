# Spec: Profile Page Backend

## Overview
Wire up the `/profile` route with real database queries, replacing the hardcoded data from Step 04. This adds helper functions in `database/db.py` to fetch the authenticated user's details, expense stats (total spent, transaction count, top category), recent transactions, and category breakdown directly from the `expenses` table. The `profile.html` template from Step 04 already expects this data structure — no template changes are needed.

## Depends on
- Step 01 — Database setup (`expenses` table must exist)
- Step 03 — Login + Logout (session auth must be working; route is logged-in-only)
- Step 04 — Profile Page (the `profile.html` template and route structure already exist)

## Routes
- **Modify** `GET /profile` — replace hardcoded data with database queries — access level: logged-in only (unchanged)

No new routes.

## Database changes
No new tables or columns. The existing `users` and `expenses` tables are sufficient.

New helper functions needed in `database/db.py`:

- `get_user_by_id(user_id)` — returns a user row for the given id (name, email, created_at), or None if not found
- `get_expense_stats(user_id)` — returns a dict with `total_spent` (float), `transaction_count` (int), and `top_category` (str, the category name with the highest total amount)
- `get_recent_expenses(user_id, limit=10)` — returns a list of expense rows (date, description, category, amount, id) ordered by date descending
- `get_category_breakdown(user_id)` — returns a list of dicts, each with `category` name, `total` amount (float), and `percentage` (float rounded to 0 dp). Percentage is calculated as (category_total / grand_total * 100). Categories with zero spend are excluded.

## Templates
No template changes. The `profile.html` template from Step 04 already expects `user`, `stats`, `transactions`, and `categories` — the data shape must match what the template renders:
- `user`: dict with `name` (str), `email` (str), `member_since` (str — formatted from `created_at`)
- `stats`: dict with `total_spent` (str — formatted "$X.XX"), `transaction_count` (int), `top_category` (str)
- `transactions`: list of dicts with `date`, `description`, `category`, `amount` (str — formatted "$X.XX")
- `categories`: list of dicts with `name`, `amount` (str — formatted "$X.XX"), `percentage` (int)

## Files to change
- `app.py` — replace all hardcoded profile data with calls to new DB helpers in the `/profile` route; format amounts as currency strings
- `database/db.py` — add `get_user_by_id()`, `get_expense_stats()`, `get_recent_expenses()`, `get_category_breakdown()` helper functions

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()`
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- All currency formatting must use Python f-strings with `:.2f` format — do not use the `locale` module
- Member-since date: read `created_at` from the database and format as "Month YYYY" (e.g. "January 2026")
- If the user has no expenses, `get_expense_stats` must return `total_spent=0`, `transaction_count=0`, `top_category="None"`; `get_recent_expenses` returns an empty list; `get_category_breakdown` returns an empty list
- Write DB helpers as standalone functions in `database/db.py` — do not use a class or ORM pattern
- Never put DB logic in route functions — all queries go in `database/db.py`
- Use `url_for()` for all internal links and redirects — no hardcoded URLs in templates or routes
- Profile route should never return a raw string — always render `profile.html` or redirect
- Import new helpers at the top of `app.py` alongside existing imports

## Definition of done
- [ ] Visiting `/profile` while logged in shows real user data (name, email from DB)
- [ ] Visiting `/profile` while logged in shows real stats (total spent, count, top category from DB expenses)
- [ ] Visiting `/profile` while logged in shows real recent transactions from the expenses table
- [ ] Visiting `/profile` while logged in shows a real category breakdown calculated from the expenses table
- [ ] Visiting `/profile` without being logged in still redirects to `/login`
- [ ] A user with no expenses sees `0`, `0`, `"None"` for stats and empty lists for transactions and categories
- [ ] Date formatting matches "Month YYYY" (e.g., "June 2026") for member-since
- [ ] All currency values are formatted as "$X.XX"
- [ ] All queries use parameterised SQL with `?` placeholders
- [ ] No hardcoded data remains in the `/profile` route
- [ ] App starts and runs on port 5001 without errors
