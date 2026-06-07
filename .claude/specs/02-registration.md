# Spec: Registration

## Overview
!gi
Implement the POST handler for `/register` so users can create an account.
The `register.html` template and `GET /register` route already exist — this step
makes the form actually work: validate input, hash the password, insert the user
into the database, create a session, and redirect to the landing page.

This is the second step in the Spendly roadmap. With registration working,
users can create accounts, which unlocks login (Step 3), profile (Step 4),
and all expense-tracking features.

## Depends on

- Step 01 — Database setup (tables and seed data exist)

## Routes

- **Modify** `GET /register` — already renders `register.html`; no structural changes needed, but may need to accept and pass an `error` template variable
- **Add** `POST /register` — processes form submission, validates input, creates user, redirects on success or re-renders form with error — access level: public

## Database changes

No new tables or columns — uses existing `users` table created in Step 01.

New helper function in `database/db.py`:
- `create_user(name, email, password)` — hashes password with werkzeug, inserts row into `users`, returns the new user id. Must catch UNIQUE constraint violation on email and raise a meaningful error.

## Templates

- **Modify:** `templates/register.html` — ensure the `error` variable is displayed correctly (template already has `{% if error %}` block); may need minor adjustments if the variable name differs

## Files to change

- `app.py` — update `/register` route to handle both GET and POST, add session import
- `database/db.py` — add `create_user()` function
- `templates/register.html` — verify or adjust error display

## Files to create

- None

## New dependencies

No new pip packages. Uses `werkzeug.security.generate_password_hash` (already in requirements.txt and already used by `seed_db()`).

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Never put DB logic in route functions — it belongs in `database/db.py`
- Use `url_for()` for all internal links and redirects
- Enable Flask sessions — set a `secret_key` on the app config
- After successful registration, log the user in by storing `user_id` in the session
- Validate: name is not empty, email looks valid, password is at least 8 characters
- Re-render the form with an error message on validation failure or duplicate email
- Never return raw strings from implemented routes

## Definition of done

- [ ] POST to `/register` with valid name/email/password creates a user in the database
- [ ] Password stored in `users.password_hash` is hashed, never plaintext
- [ ] Duplicate email returns an error message (no crash, no duplicate row)
- [ ] Empty name, invalid email, or short password returns an error message
- [ ] Successful registration stores `user_id` in the Flask session
- [ ] Successful registration redirects to `GET /` (landing page)
- [ ] All queries use parameterised SQL
- [ ] App starts and runs on port 5001 without errors
