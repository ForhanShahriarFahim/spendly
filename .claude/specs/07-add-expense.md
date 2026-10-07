# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` stub with a working form so a logged-in user
can record a new expense (amount, category, date, optional description). Until
now the only expenses in the app are the seeded demo rows, so the profile page
cannot reflect real usage. This step is the first write path for the `expenses`
table: it validates the submitted form, inserts a row owned by the current user
through a new helper in `database/db.py`, and redirects back to `/profile`,
where the new expense appears in the summary, category breakdown and recent
transactions.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` constant, `get_db()`)
- Step 2/3: Registration and login/logout (session `user_id`, `_current_user()`)
- Step 4–6: Profile page and its read helpers (the redirect target that must
  show the new expense)

## Routes
- `GET /expenses/add` — render the add-expense form (date defaults to today) —
  logged-in (redirects to `/login` when logged out)
- `POST /expenses/add` — validate the form, insert the expense for the current
  user, redirect to `/profile` — logged-in (redirects to `/login` when logged
  out)

The existing `add_expense` view in `app.py` is changed from a raw-string stub
to accept `GET` and `POST` and render a template. Edit and delete stubs
(Steps 8 and 9) are not touched.

## Database changes
No schema changes. The existing `expenses` table already has `user_id`,
`amount`, `category`, `date`, `description` and `created_at`.

One new helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts a
  row with a parameterised query, commits, returns `cursor.lastrowid`. The
  `description` is stored as `NULL` when blank.

The existing `CATEGORIES` tuple is reused as the single source of truth for
allowed categories (imported into `app.py`, passed to the template).

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with
  amount (`type="number"`, `step="0.01"`, `min="0.01"`), category `<select>`
  built from `CATEGORIES`, date (`type="date"`), description (`type="text"`,
  optional), a submit button and a "Cancel" link back to the profile. Shows an
  inline error message and re-fills submitted values on validation failure.
  All links via `url_for()`.
- **Modify:** `templates/profile.html` — add an "Add Expense" link/button
  (`url_for('add_expense')`) in the header area, and make the empty-state
  ("No expenses yet") point to the add form.

## Files to change
- `app.py` — import `CATEGORIES` and `create_expense`; replace the `add_expense`
  stub with a GET/POST view (auth guard, validation, insert, redirect)
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — add the "Add Expense" entry points
- `static/css/profile.css` — style for the new profile button (CSS variables
  only), if not covered by existing button styles
- `CLAUDE.md` — update the routes table: `GET/POST /expenses/add` implemented;
  mention `create_expense()` in the db.py helper list

## Files to create
- `templates/add_expense.html`
- `static/css/expense_form.css` — page-specific styles for the form (linked from
  the template, not inline); only if existing `style.css` form styles are not
  sufficient
- `tests/test_add_expense.py` — pytest coverage for the route and helper

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route validates input, calls
  `create_expense()`, and redirects
- Use `url_for()` for every link and redirect — never hardcode URLs
- Use `abort()` for HTTP errors, not raw string returns; validation problems are
  re-rendered inline with an error message (status 200, matching the register
  and login pattern)
- The expense is always saved with `user_id = session["user_id"]`; never read a
  user id from the form
- Validation (server-side, in `app.py`):
  - `amount`: required, must parse as a number, finite (reject `nan`/`inf`),
    greater than 0; round to 2 decimal places
  - `category`: must be one of `CATEGORIES`
  - `date`: required, valid `YYYY-MM-DD` (reuse `_parse_iso_date`); future dates
    are allowed unless the project decides otherwise — not rejected in this step
  - `description`: optional, trimmed, max 200 characters
- Do not implement Step 8 (edit) or Step 9 (delete) stubs
- Vanilla JS only; the form must work with JS disabled
- Amounts display with the ₹ symbol, consistent with the profile page
- Jinja autoescaping stays on; never mark user-supplied description as `|safe`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Posting to `/expenses/add` while logged out redirects to `/login` and
  inserts nothing
- [ ] Visiting `/expenses/add` while logged in renders the form with all seven
  categories in the dropdown and the date pre-filled with today
- [ ] Submitting a valid expense redirects to `/profile` and the expense appears
  in Recent Transactions with the correct amount, category, date and description
- [ ] After adding, the profile total spent, transaction count and category
  breakdown reflect the new expense
- [ ] The saved row belongs to the logged-in user and is not visible to other
  users
- [ ] Submitting with an empty, non-numeric, zero, negative, `nan` or `inf`
  amount re-renders the form with an inline error and saves nothing
- [ ] Submitting a category not in the list (tampered POST) shows an error and
  saves nothing
- [ ] Submitting a missing or malformed date shows an error and saves nothing
- [ ] A description longer than 200 characters shows an error and saves nothing
- [ ] A blank description is accepted and stored as `NULL`
- [ ] After a validation error, previously entered values are preserved in the
  form
- [ ] An `<script>` tag entered as the description is displayed escaped on the
  profile page
- [ ] The profile page shows an "Add Expense" link that leads to the form, and
  the "Cancel" link on the form returns to `/profile`
- [ ] `GET /expenses/<id>/edit` and `/expenses/<id>/delete` still return their
  stub responses
- [ ] `pytest` passes, including the new `tests/test_add_expense.py`
