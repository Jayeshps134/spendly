# Spec: Date Filter for Profile Page

## Overview
Add date range filtering to the `/profile` page so users can view their expenses, stats, and category breakdown for a specific period. The transaction history table gets date picker inputs ("from" and "to") that re-render the page with filtered results when submitted. All three data sections — summary stats, transaction history, and category breakdown — reflect the chosen date range.

## Depends on
- Step 01 — Database setup (`expenses` table must exist with a `date` column)
- Step 03 — Login + Logout (session auth must be working; profile is a protected route)
- Step 04 — Profile Page (the `profile.html` template and HTML structure exist)
- Step 05 — Profile Page Backend (DB helpers exist and return the expected data shapes)

## Routes
- **Modify** `GET /profile` — support optional `start_date` and `end_date` query parameters; pass them through to filtered DB helpers — access level: logged-in only (unchanged)

No new routes.

## Database changes
No new tables or columns. The existing `expenses` table's `date` column (stored as TEXT in `YYYY-MM-DD` format) supports string-comparison filtering directly.

New helper functions needed in `database/db.py`:

- `get_expense_stats(user_id, start_date=None, end_date=None)` — **modify existing** to accept optional date range params; apply to the WHERE clause when provided
- `get_expenses_by_date_range(user_id, start_date, end_date)` — returns a list of expense rows (id, date, description, category, amount) within the given date range (inclusive), ordered by date descending
- `get_category_breakdown(user_id, start_date=None, end_date=None)` — **modify existing** to accept optional date range params; apply to the WHERE clause when provided

## Templates
- **Modify:** `templates/profile.html` — add a date filter form above the transaction history table with:
  - A "From" date input (`<input type="date">`, name=`start_date`)
  - A "To" date input (`<input type="date">`, name=`end_date`)
  - A "Filter" submit button
  - A "Clear" link/button that resets the filter (links back to `/profile` without query params)
  - Pre-fill inputs with the current filter values when a filter is active
  - Show an indicator or message like "Showing expenses from {start_date} to {end_date}" when a filter is active

## Files to change
- `app.py` — update the `/profile` route to read `start_date` and `end_date` from `request.args` and pass them to DB helpers
- `database/db.py` — modify `get_expense_stats()` and `get_category_breakdown()` to accept optional `start_date` and `end_date` parameters; add new `get_expenses_by_date_range()` function
- `templates/profile.html` — add the date filter UI elements

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()`
- Parameterised queries only — never f-strings in SQL; append `AND date >= ?` / `AND date <= ?` with dynamic parameters
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- Date format in the template is `YYYY-MM-DD` for input values and display; dates come from the DB already in this format
- The filter form must use `GET` method (not POST) so the URL carries the filter state and is shareable/bookmarkable
- When no date filter params are provided, `get_expenses_by_date_range` is not called — fall back to the existing `get_recent_expenses` (unfiltered)
- If only `start_date` is provided, filter from that date to the present
- If only `end_date` is provided, filter from the earliest expense to that date
- Empty filter results must be handled gracefully — show a "No expenses found in this date range" message rather than an empty table
- Date validation: if `start_date > end_date`, treat it as no filter (show all expenses) — or swap them
- Always use `url_for()` for internal links and redirects — no hardcoded URLs in templates or routes
- New and modified DB helpers follow the same patterns (connection lifecycle, error handling) as existing helpers in `database/db.py`
- Import `get_expenses_by_date_range` at the top of `app.py` alongside existing imports

## Definition of done
- [ ] The `/profile` page shows date inputs ("From" and "To") above the transaction history
- [ ] Submitting the filter with a date range updates the transaction list to show only expenses in that range
- [ ] The summary stats (total spent, transaction count, top category) update to reflect the filtered date range
- [ ] The category breakdown updates to reflect the filtered date range
- [ ] A "Clear" button/link resets the filter and shows all expenses
- [ ] When a filter is active, the date inputs are pre-filled with the current filter values
- [ ] A message like "Showing expenses from YYYY-MM-DD to YYYY-MM-DD" appears when a filter is active
- [ ] When no filter is applied, the page behaves exactly as before (shows all transactions via `get_recent_expenses`)
- [ ] When no expenses match the filter, a "No expenses found in this date range" message replaces the transaction table
- [ ] Filtering with only `start_date` shows expenses from that date onward
- [ ] Filtering with only `end_date` shows expenses up to that date
- [ ] The filter form uses GET and the URL contains `?start_date=...&end_date=...`
- [ ] All queries use parameterised SQL with `?` placeholders
- [ ] App starts and runs on port 5001 without errors
