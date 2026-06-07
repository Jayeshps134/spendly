# Spec: Login

## Overview
Implement the POST handler for `/login` so users can authenticate with their email and password, and implement `/logout` to end the session. The `login.html` template and `GET /login` route already exist — this step makes the form functional: look up the user by email, verify the password hash, store `user_id` in the session, and redirect to the landing page. Logout clears the session and redirects to the landing page.

This is the third step in the Spendly roadmap. With login and logout working, the authentication loop (register → login → logout) is complete, unlocking profile (Step 4) and all expense-tracking features.

## Depends on

- Step 02 — Registration (`create_user()` and password hashing exist)

## Routes

- **Modify** `POST /login` — processes form submission, validates input, authenticates user, sets session, redirects on success or re-renders form with error — access level: public
- **Modify** `GET /logout` — clears session (removes `user_id`) and redirects to `GET /` — access level: logged-in

## Database changes

No new tables or columns — uses existing `users` table created in Step 01.

New helper function in `database/db.py`:
- `get_user_by_email(email)` — returns a user row (dict-like `sqlite3.Row`) for the given email, or `None` if no match. Used by the login route to look up the user before verifying the password.

## Templates

- **Modify:** `templates/login.html` — change form `action` from `action="/login"` to `action="{{ url_for('login') }}"` to avoid hardcoded URLs
- **Modify:** `templates/base.html` — update the nav links to conditionally show "Logout" (and user greeting) when `session.user_id` is set, instead of always showing "Sign in" and "Get started"

## Files to change

- `app.py` — update `/login` route to handle both GET and POST; replace `/logout` stub with real implementation; add `session` usage for login state
- `database/db.py` — add `get_user_by_email()` helper
- `templates/login.html` — fix hardcoded `action` URL to use `url_for()`
- `templates/base.html` — conditional nav links based on login state

## Files to create

- None

## New dependencies

No new pip packages. Uses `werkzeug.security.check_password_hash` (already in requirements.txt, sibling to `generate_password_hash` already used by `seed_db()` and `create_user()`).

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Never put DB logic in route functions — it belongs in `database/db.py`
- Use `url_for()` for all internal links and redirects — no hardcoded URLs in templates or routes
- After successful login, store `user_id` in the session
- Validate: email is not empty, password is not empty
- Re-render the form with an error message on invalid credentials or missing fields
- Never reveal whether an email exists — use a generic error like "Invalid email or password"
- After logout, clear the entire session (not just `user_id`) with `session.clear()`
- Never return raw strings from implemented routes — always render a template or redirect

## Definition of done

- [ ] POST to `/login` with valid email/password sets `user_id` in the session
- [ ] POST to `/login` with valid email/password redirects to `GET /`
- [ ] POST to `/login` with incorrect password returns "Invalid email or password" error
- [ ] POST to `/login` with non-existent email returns "Invalid email or password" error (same generic message)
- [ ] POST to `/login` with empty email or password returns an appropriate error
- [ ] `GET /logout` clears the session and redirects to `GET /`
- [ ] After login, the navbar shows a logout link instead of "Sign in" / "Get started"
- [ ] After logout, the navbar reverts to showing "Sign in" / "Get started"
- [ ] All queries use parameterised SQL
- [ ] `login.html` form action uses `url_for('login')` not a hardcoded `/login`
- [ ] App starts and runs on port 5001 without errors
