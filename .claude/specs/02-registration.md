# Spec: Registration

## Overview
Turn the existing `GET /register` page into a working sign-up flow. A visitor submits name, email and password; the server validates the input, stores the user with a hashed password, show success message and redirects to the login page. This is the first write path into the `users` table created in Step 1, and it must exist before login (and later logout/profile) can be built.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form (already implemented, unchanged behaviour) — public
- `POST /register` — validate form, create user, redirect to `/login` on success; re-render the form with an error on failure — public

Both methods are served by the same `register` view (`methods=["GET", "POST"]`).

## Database changes
No database changes. The `users` table already has `name`, `email` (UNIQUE), `password_hash` and `created_at`.

New helpers in `database/db.py` (DB logic must not live in routes):
- `get_user_by_email(email)` — returns a `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row, returns the new user id; raises `sqlite3.IntegrityError` if the email is already taken

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Form `action` uses `url_for('register')` instead of the hardcoded `/register`
  - Re-populate `name` and `email` inputs from the submitted values on error (never re-populate the password)
  - Keep the existing `{% if error %}` block for displaying errors

## Files to change
- `app.py` — accept POST on `register`, call the db helpers, redirect via `url_for('login')`
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — see above
- `CLAUDE.md` — update the routes table to show `POST /register` as implemented

## Files to create
- `tests/test_registration.py` — pytest coverage for the cases in the Definition of done

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Route function stays thin: read form, call db helpers, render or redirect
- Use `url_for()` for every internal link and redirect
- Validation (server-side, in this order):
  - name: trimmed, non-empty
  - email: trimmed, lower-cased, non-empty, contains `@`
  - password: at least 8 characters (matches the form placeholder)
  - email not already registered
- Detect duplicates via `get_user_by_email()` and also catch `sqlite3.IntegrityError` from `create_user()` to cover races
- Validation failures re-render `register.html` with an `error` message and HTTP 200 (no `abort()`; the form is the right place to show the error)
- Do not start a session or log the user in — sessions arrive with login. Do not add a `secret_key` or flash messages in this step
- Do not implement `/login` POST, `/logout` or any other stub route

## Definition of done
- [ ] `GET /register` still renders the form with a 200
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is not the plain password and verifies with `check_password_hash`
- [ ] Email is stored trimmed and lower-cased; registering `A@x.com` then `a@x.com` is rejected as a duplicate
- [ ] Registering with an existing email (e.g. `demo@spendly.com`) re-renders the form with a visible error and creates no new row
- [ ] Empty name, empty/invalid email, or a password shorter than 8 characters each re-render the form with a specific error and create no row
- [ ] On error, the name and email fields keep what the user typed; the password field is empty
- [ ] No hardcoded `/register` or hex colours were added; the form posts via `url_for('register')`
- [ ] `pytest` passes, including the new `tests/test_registration.py`
- [ ] App starts on port 5001 without errors
