# Spec: Profile Page Design

## Overview
Replace the placeholder behind `GET /profile` with a real, logged-in-only account page. It shows who the user is (avatar initial, name, email, member-since date), three headline stats (total spent, expense count, top category), the ten most recent expenses, and a per-category spending breakdown. It is read-only: it consumes existing `users` and `expenses` data and gives users the first view of their own spending, ahead of the expense CRUD routes (Steps 7–9). This spec documents the Step 4 work as implemented on `feature/profile-page-design`.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `seed_db()`)
- Step 2 — Registration (users with hashed passwords)
- Step 3 — Login and Logout (`session["user_id"]`, `_current_user()`, session-aware navbar)

## Routes
- `GET /profile` — render `profile.html` with the user's details, summary, category breakdown and recent expenses; redirect to `/login` when logged out or when the session's user no longer exists (session cleared) — logged-in

No other new routes.

## Database changes
No schema changes. Four new read-only helpers in `database/db.py`, all parameterised and scoped to one `user_id`:
- `get_user_profile(user_id)` — name, email, `created_at`; `None` if the user does not exist
- `get_expense_summary(user_id)` — `total` and `count` (zero values when the user has no expenses)
- `get_category_breakdown(user_id)` — per-category `total` and `count`, ordered highest total first
- `get_recent_expenses(user_id, limit=10)` — newest first

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; header, stat cards, recent-expenses table, category list with `<progress>` bars, and an empty state when the user has no expenses
- **Modify:**
  - `templates/base.html` — adds the `{% block head %}` hook (if needed) so page-specific stylesheets can be linked, and links the navbar user name to `url_for('profile')`

## Files to change
- `app.py` — implement `profile()` route, import the new db helpers
- `database/db.py` — add the four read-only helpers above
- `static/css/style.css` — small global tweaks needed by the navbar/profile link
- `templates/base.html` — see above
- `CLAUDE.md` — mark `GET /profile` implemented and list the new db helpers

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — profile-only styles
- `tests/test_profile.py` — pytest coverage for the Definition of done

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password data is read or displayed on this page)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Page-specific styles go in `static/css/profile.css`, not inline `<style>` tags
- Route stays thin: check session, call db helpers, render template
- All DB logic lives in `database/db.py`, never in the route
- Every query is filtered by the session's `user_id`; a user must never see another user's data
- Use `url_for()` for every internal link and redirect — no hardcoded URLs
- Vanilla JS only; this page needs no JavaScript
- Escape all user-supplied text via Jinja2 autoescape (no `|safe`)
- Do not implement `/expenses/add`, `/expenses/<id>/edit` or `/expenses/<id>/delete`; do not add edit/delete controls to the page
- Do not change the port (5001)

## Definition of done
- [ ] `GET /profile` while logged out returns a 302 to `/login`
- [ ] `GET /profile` for a session whose user was deleted clears the session and redirects to `/login`
- [ ] Logged in as `demo@spendly.com` / `demo123`, `/profile` returns 200 and shows the user's name, email and "Member since" date
- [ ] The avatar shows the first letter of the user's name in upper case
- [ ] Stat cards show total spent (2 decimals), expense count and top category, and match the seeded data
- [ ] The recent-expenses table lists at most 10 rows, newest first, with date, description (or "—" if empty), category and amount
- [ ] The category list is ordered highest spend first, each row showing total, count (correct singular/plural) and a progress bar whose value is that category's share of total spending
- [ ] A user with no expenses sees "No expenses yet" and "—" as top category, with no table or breakdown
- [ ] A user never sees another user's expenses
- [ ] The navbar user name links to `/profile` via `url_for('profile')`
- [ ] The page is usable at mobile width (no horizontal page scroll; the table scrolls within its wrapper)
- [ ] No hardcoded URLs or hex colours were added in `profile.html` or `profile.css`
- [ ] `pytest` passes, including `tests/test_profile.py`
- [ ] App starts on port 5001 without errors
