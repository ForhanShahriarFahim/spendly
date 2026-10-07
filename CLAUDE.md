# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture
```
spendly/
├── app.py              # All routes — single file, no blueprints
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db()
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   ├── landing.css     # Landing-page-only styles
│   │   └── profile.css     # Profile-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
└── requirements.txt
```

**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration 
  before implementing any new feature
- Always use a subagent to verify test results 
  after any implementation
- When asked to plan, delegate codebase research 
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

---

## Commands
```bash
# Setup
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run dev server (port 5001)
python app.py

# Run all tests
pytest

# Run a specific test file
pytest tests/test_foo.py

# Run a specific test by name
pytest -k "test_name"

# Run tests with output visible
pytest -s
```

---

## Implemented vs stub routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET /register` | Implemented — renders `register.html` |
| `POST /register` | Implemented — validates, creates user, redirects to `/login?registered=1` |
| `GET /login` | Implemented — renders `login.html` (shows success banner when `registered=1`); redirects to `/profile` if logged in |
| `POST /login` | Implemented — verifies credentials, starts session (`user_id`), redirects to `/profile` |
| `GET /logout` | Implemented — clears session, redirects to `/` |
| `GET /profile` | Implemented — renders `profile.html`; redirects to `/login` when logged out; optional `date_from`/`date_to` (`YYYY-MM-DD`, inclusive) query params filter all sections |
| `GET /analytics` | Implemented — renders `analytics.html` ("Coming Soon" page); redirects to `/login` when logged out; navbar link visible to logged-in users only, with active state |
| `GET /expenses/add` | Implemented — renders `add_expense.html`; redirects to `/login` when logged out |
| `POST /expenses/add` | Implemented — validates amount/category/date/description, inserts via `create_expense()`, redirects to `/profile`; re-renders form with inline error on invalid input |
| `GET /expenses/<id>/edit` | Implemented — renders `edit_expense.html` pre-filled; redirects to `/login` when logged out; 404 for a missing or other user's expense |
| `POST /expenses/<id>/edit` | Implemented — validates via `_validate_expense_form()`, updates via `update_expense()`, redirects to `/profile`; re-renders form with inline error on invalid input; 404 for a missing or other user's expense |
| `GET /expenses/<id>/delete` | Stub — Step 9 |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **`database/db.py` is implemented (Step 1)** — `get_db()`, `init_db()`, `seed_db()` exist, plus the user helpers, `create_expense()` and `update_expense()` (the expense write helpers), `get_expense()` (ownership-scoped single-expense read) and the read-only profile helpers (`get_user_profile()`, `get_expense_summary()`, `get_category_breakdown()`, `get_recent_expenses()`; the last three take optional `date_from`/`date_to` bounds via the private `_date_filter()`); the DB file is `expense_tracker.db` in the project root (gitignored), created and seeded on app startup. Do not assume any other DB helpers exist until the step that implements them
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- **Sessions** use `app.secret_key` from the `SECRET_KEY` env var (dev-only fallback in `app.py`); the session stores only `user_id`
- The app runs on **port 5001**, not the Flask default 5000 — don't change this