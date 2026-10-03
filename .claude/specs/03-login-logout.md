# Spec: Login and Logout

## Overview
Turn the existing `GET /login` page into a working sign-in flow and replace the `/logout` stub. A visitor submits email and password; the server verifies them against the hashed password stored in `users`, starts a Flask session, and redirects. Logout clears the session. This is the first use of sessions in Spendly and is required before the profile page (Step 4) and expense routes (Steps 7–9) can be restricted to logged-in users.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`)
- Step 2 — Registration (`get_user_by_email()`, users with hashed passwords, `/login?registered=1` banner)

## Routes
- `GET /login` — render the sign-in form (existing); if already logged in, redirect to `/` — public
- `POST /login` — validate credentials, start session, redirect to `/` on success; re-render the form with an error on failure — public
- `GET /logout` — clear the session and redirect to `/` — logged-in (a logged-out visitor is simply redirected to `/`)

`GET` and `POST /login` are served by the same `login` view (`methods=["GET", "POST"]`).

## Database changes
No database changes. Uses the existing `users` table and the existing `get_user_by_email()` helper.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Form `action` uses `url_for('login')` instead of the hardcoded `/login`
    - Re-populate the `email` input from the submitted value on error (never the password)
    - Keep the existing `{% if error %}` and `{% if registered %}` blocks
  - `templates/base.html`
    - Navbar is session-aware: when logged in, show the user's name and a "Sign out" link (`url_for('logout')`); when logged out, keep "Sign in" / "Get started"

## Files to change
- `app.py` — set `app.secret_key`, accept POST on `login`, implement `logout`, expose the current user to templates (e.g. a context processor)
- `templates/login.html` — see above
- `templates/base.html` — see above
- `CLAUDE.md` — update the routes table: `POST /login` and `GET /logout` implemented

## Files to create
- `tests/test_login_logout.py` — pytest coverage for the cases in the Definition of done

## New dependencies
No new dependencies. Flask's built-in `session` and werkzeug's `check_password_hash` are used.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`; never log or echo the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Route functions stay thin: read form, call db helpers, set/clear session, render or redirect
- Any new DB lookup (e.g. `get_user_by_id()` for the navbar name) goes in `database/db.py`, not in routes
- Use `url_for()` for every internal link and redirect
- Normalize the email (trim + lower-case) before lookup, same as registration
- Store only `user_id` in the session (and optionally the name); never the password hash
- Secret key: read from an environment variable (e.g. `SECRET_KEY`) with a clearly-labelled development fallback; do not hardcode a production secret
- Use one generic error ("Invalid email or password.") for both unknown email and wrong password — do not reveal which was wrong
- Validation failures re-render `login.html` with an `error` and HTTP 200 (no `abort()`)
- Logout must clear the whole session (`session.clear()`)
- Do not implement `/profile`, expense routes, or any other stub; do not add route-protection decorators in this step
- Do not add flash messages; keep using template variables as in registration

## Definition of done
- [ ] `GET /login` still renders the form with a 200 and shows the success banner for `?registered=1`
- [ ] Logging in as `demo@spendly.com` / `demo123` returns a 302 to `/` and the navbar then shows the user's name and a "Sign out" link
- [ ] Email matching is case- and whitespace-insensitive (`  DEMO@Spendly.com ` logs in)
- [ ] A wrong password and an unknown email both re-render the form with the same "Invalid email or password." error and set no session
- [ ] Empty email or password re-renders the form with an error and sets no session
- [ ] On error the email field keeps what the user typed; the password field is empty
- [ ] Visiting `/login` while logged in redirects to `/`
- [ ] `GET /logout` while logged in clears the session, redirects (302) to `/`, and the navbar shows "Sign in" / "Get started" again
- [ ] `GET /logout` while logged out does not error and redirects to `/`
- [ ] The session cookie does not contain the plain password or password hash
- [ ] No hardcoded `/login`, `/logout` or hex colours were added; links and forms use `url_for()`
- [ ] `pytest` passes, including the new `tests/test_login_logout.py`
- [ ] App starts on port 5001 without errors
