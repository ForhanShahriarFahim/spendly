# Spec: Backend Connection

## Overview
Step 5 finishes wiring the `/profile` page to live data. Step 4 already moved
the page onto real queries in `database/db.py`; this step closes the remaining
gaps: "Member since" is formatted as "Month YYYY", and category percentages are
integers that sum to exactly 100 and are shown as visible text beside each
progress bar. Every logged-in user sees only their own data.

## Depends on
- Step 1: Database setup (tables and `get_db()` exist)
- Step 2: Registration (users are stored in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page (template renders all four sections from DB helpers)

## Routes
No new routes. The existing `GET /profile` route is unchanged.

## Database changes
No schema changes. All DB logic stays in `database/db.py` (no `queries.py`):
- `get_user_profile(user_id)` → dict with `id`, `name`, `email`, `created_at`
  and new `member_since` ("Month YYYY"); `None` if the user does not exist
- `get_expense_summary(user_id)` → `{"total", "count"}`; zeros when no expenses
- `get_recent_expenses(user_id, limit=10)` → rows with `id`, `amount`,
  `category`, `date`, `description`, newest first
- `get_category_breakdown(user_id)` → dicts with `category`, `total`, `count`
  and new `pct` (int), highest total first; `[]` when no expenses

## Templates
- **Modify**: `templates/profile.html`
  - "Member since" uses `user["member_since"]`.
  - Category rows use `cat["pct"]` and show it as visible text next to the bar.
  - Amounts keep the ₹ symbol.

## Files to change
- `database/db.py`, `templates/profile.html`, `static/css/profile.css`
- `tests/test_profile.py` (updated expectations)

## Files to create
- `tests/test_backend_connection.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only
- Use CSS variables — never hardcode hex values; no inline styles
- All templates extend `base.html`
- Currency always displays as ₹
- `pct` values are integers using half-up rounding and sum to 100; the largest
  category absorbs any rounding remainder
- No expenses → zeros and empty lists, never an exception

## Seed data reference (demo@spendly.com)
8 expenses totalling 230.79. By category: Bills 85.00 (37%), Shopping 49.90
(22%), Food 44.90 (19%), Health 24.99 (11%), Entertainment 15.00 (6%),
Other 7.25 (3%), Transport 3.75 (2%). Top category: Bills.

## Definition of done
- [ ] Logging in as demo@spendly.com / demo123 shows "Demo User", "demo@spendly.com" and "Member since <Month YYYY>"
- [ ] Total spent is ₹230.79, expense count is 8, top category is Bills
- [ ] Recent expenses are listed newest first
- [ ] Category breakdown shows 7 categories with visible percentages summing to 100
- [ ] All amounts display the ₹ symbol
- [ ] A brand-new user sees ₹0.00, 0 expenses and no breakdown — no errors
- [ ] `pytest` passes
