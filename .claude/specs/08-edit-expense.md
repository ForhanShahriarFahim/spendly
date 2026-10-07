# Spec: Edit Expense

## Overview
Step 8 replaces the `/expenses/<id>/edit` stub with a working form so a logged-in
user can correct an existing expense (amount, category, date, description). Step 7
gave users a way to record expenses; mistakes and changed details can currently
not be fixed. This step adds the first update path for the `expenses` table: it
loads the expense (only if it belongs to the current user), pre-fills the form,
validates the submission with the same rules as Step 7, updates the row through a
new helper in `database/db.py`, and redirects back to `/profile`. The profile's
Recent expenses table gains an "Edit" link per row as the entry point.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES`, `get_db()`)
- Step 2/3: Registration and login/logout (session `user_id`, `_current_user()`)
- Step 4–6: Profile page and its read helpers (entry point and redirect target)
- Step 7: Add expense (`_validate_expense_form()`, `_render_add_expense()` pattern,
  `add_expense.html`)

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the expense's
  current values — logged-in (redirects to `/login` when logged out; 404 when the
  expense does not exist or belongs to another user)
- `POST /expenses/<int:id>/edit` — validate the form, update the expense, redirect
  to `/profile` — logged-in (redirects to `/login` when logged out; 404 when the
  expense does not exist or belongs to another user)

The existing `edit_expense` view in `app.py` is changed from a raw-string stub to
accept `GET` and `POST` and render a template. The delete stub (Step 9) is not
touched.

## Database changes
No schema changes.

Two new helpers in `database/db.py`:
- `get_expense(expense_id, user_id)` — returns the row (id, amount, category,
  date, description) only if it exists **and** is owned by `user_id`, else `None`.
  Parameterised query.
- `update_expense(expense_id, user_id, amount, category, date, description)` —
  `UPDATE ... WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was
  changed (`cursor.rowcount > 0`), else `False`. A blank description is stored as
  `NULL`. `user_id` and `created_at` are never modified.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; same fields,
  labels and error display as `add_expense.html`, pre-filled from the expense;
  form posts to `url_for('edit_expense', id=expense_id)`; submit button "Save
  changes"; "Cancel" link back to `url_for('profile')`. Re-fills submitted values
  on validation failure.
- **Modify:** `templates/profile.html` — add an "Actions" column to the Recent
  expenses table with an "Edit" link per row
  (`url_for('edit_expense', id=e["id"])`).

## Files to change
- `app.py` — import `get_expense` and `update_expense`; replace the `edit_expense`
  stub with a GET/POST view (auth guard, ownership check via `abort(404)`,
  validation via `_validate_expense_form()`, update, redirect); import `abort`
- `database/db.py` — add `get_expense()` and `update_expense()`
- `templates/profile.html` — add the Edit link column
- `static/css/profile.css` — style for the Edit link / actions column (CSS
  variables only)
- `CLAUDE.md` — routes table: `GET/POST /expenses/<id>/edit` implemented; add
  `get_expense()` and `update_expense()` to the db.py helper list

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py` — pytest coverage for the route and helpers

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route validates input, calls the
  helpers, and redirects
- Use `url_for()` for every link and redirect — never hardcode URLs
- Use `abort(404)` for a missing or foreign expense — never reveal whether an id
  belongs to another user (same response for both cases)
- Ownership is enforced in SQL (`AND user_id = ?`) for both read and update; the
  user id always comes from `session["user_id"`], never from the form
- Reuse `_validate_expense_form()` unchanged so add and edit share identical
  rules (amount > 0, finite, ≤ max; valid category; valid date; description ≤ 200)
- Validation errors re-render the form inline with status 200, matching the add,
  register and login pattern
- Do not implement Step 9 (delete); `/expenses/<id>/delete` keeps its stub
- Vanilla JS only; the form must work with JS disabled
- Amounts display with the ₹ symbol, consistent with the profile page
- Jinja autoescaping stays on; never mark user-supplied description as `|safe`
- Prefer extracting the shared form markup rather than duplicating it if it can be
  done without breaking `add_expense.html` (optional; duplication is acceptable)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Posting to `/expenses/<id>/edit` while logged out redirects to `/login` and
  changes nothing
- [ ] The profile Recent expenses table shows an "Edit" link on every row that
  leads to the matching `/expenses/<id>/edit`
- [ ] The edit form is pre-filled with the expense's current amount, category,
  date and description (blank description shows an empty field)
- [ ] Submitting valid changes redirects to `/profile` and the updated values
  appear in Recent expenses
- [ ] After editing, the profile total spent and category breakdown reflect the
  new amount/category (old category count drops, new one rises)
- [ ] Editing does not create a new row (transaction count is unchanged)
- [ ] Visiting or posting to the edit URL of a non-existent id returns 404
- [ ] Visiting or posting to the edit URL of another user's expense returns 404
  and the other user's expense is unchanged
- [ ] Submitting an empty, non-numeric, zero, negative, `nan` or `inf` amount
  re-renders the form with an inline error and does not modify the row
- [ ] Submitting a category not in the list (tampered POST) shows an error and
  does not modify the row
- [ ] Submitting a missing or malformed date shows an error and does not modify
  the row
- [ ] A description longer than 200 characters shows an error and does not modify
  the row
- [ ] Clearing the description is accepted and stored as `NULL`
- [ ] After a validation error, the submitted values are preserved in the form
- [ ] A `<script>` tag entered as the description is displayed escaped on the
  profile page
- [ ] The "Cancel" link returns to `/profile`
- [ ] `GET /expenses/<id>/delete` still returns its stub response
- [ ] `pytest` passes, including the new `tests/test_edit_expense.py`
