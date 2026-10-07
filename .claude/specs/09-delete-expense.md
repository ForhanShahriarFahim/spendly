# Spec: Delete Expense

## Overview
Step 9 replaces the `GET /expenses/<id>/delete` stub (currently a raw string) with a real delete feature. A logged-in user clicks "Delete" on an expense row in the profile page, lands on a confirmation page showing that expense's details, and confirms with a POST. The expense is removed and the user is redirected to `/profile`. The confirmation page works without JavaScript, and a GET request never changes data.

## Depends on
- Step 1 — Database setup (`get_db()`, `expenses` table)
- Step 5 — Profile backend (profile page lists expenses)
- Step 7 — Add expense
- Step 8 — Edit expense (`get_expense()` ownership-scoped read, inline login guard pattern)

## Routes
- `GET /expenses/<int:id>/delete` — renders `delete_expense.html` confirmation page with the expense's details; never mutates data — logged-in (redirects to `/login` when logged out; `abort(404)` for a missing or other user's expense)
- `POST /expenses/<int:id>/delete` — deletes the expense via `delete_expense()` and redirects to `/profile` — logged-in (redirects to `/login` when logged out, deleting nothing; `abort(404)` for a missing or other user's expense, including a repeated POST on an already-deleted id)

This replaces the existing stub. No other stub routes are touched.

## Database changes
No schema changes. Verified against `database/db.py`: the `expenses` table needs no new columns or constraints.

Add one helper to `database/db.py`:
- `delete_expense(expense_id, user_id)` — runs `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, returns `cursor.rowcount > 0`. Opens its own connection via `get_db()` and closes it in `try/finally`, like `update_expense()`.

Because the route function is also named `delete_expense`, import the helper under an alias in `app.py` (the route name must stay `delete_expense` for `url_for`).

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; shows the expense's description, amount, category and date; a `POST` form to `url_for('delete_expense', id=...)` with a danger-styled "Delete" button; a "Cancel" link to `url_for('profile')`.
- **Modify:** `templates/profile.html` — in the `<td class="actions">` cell of each expense row, add a "Delete" link (`class="expense-delete-link"`, `href="{{ url_for('delete_expense', id=e['id']) }}"`, with an `aria-label`) next to the existing Edit link.

## Files to change
- `app.py` — replace the delete stub with the GET/POST route; import the db helper with an alias
- `database/db.py` — add `delete_expense()`
- `templates/profile.html` — add the Delete link
- `static/css/profile.css` — add `.expense-delete-link` and `.btn-danger` styles
- `tests/test_edit_expense.py` — remove `test_delete_stub_unchanged` (it asserts the old stub text)
- `CLAUDE.md` — update the `/expenses/<id>/delete` row in the routes table (GET + POST, implemented) and add `delete_expense()` to the `db.py` helper list

## Files to create
- `templates/delete_expense.html`
- `tests/test_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug (unchanged by this step)
- Use CSS variables — never hardcode hex values (use `--danger` / `--danger-light`)
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route fetches, renders or redirects, done
- Enforce ownership in SQL (`AND user_id = ?`); a missing or foreign id gives `abort(404)` with the same response
- `GET` must never delete anything; only `POST` mutates
- Use `url_for()` for every link and form action — never hardcode URLs
- Use the same inline `_current_user()` guard as the other protected routes, on both GET and POST
- Vanilla JS only; `main.js` is not needed because confirmation is a server-rendered page
- Do not add flash messages or CSRF protection in this step (app-wide gaps, out of scope)
- Do not implement any other stub route

## Definition of done
- [ ] Each expense row on `/profile` shows a "Delete" link next to "Edit"
- [ ] Clicking "Delete" opens `/expenses/<id>/delete` showing that expense's description, amount, category and date
- [ ] Opening the confirmation page (GET) does not delete the expense
- [ ] "Cancel" returns to `/profile` and the expense is still listed
- [ ] Confirming removes the expense, redirects to `/profile`, and it no longer appears in the list or totals
- [ ] Visiting `/expenses/<id>/delete` while logged out (GET or POST) redirects to `/login` and deletes nothing
- [ ] Another user's expense id returns 404 for GET and POST, and that expense is not deleted
- [ ] A nonexistent id returns 404, and a second POST on an already-deleted id returns 404
- [ ] `delete_expense()` returns `True` when a row is deleted and `False` for a missing id or a different `user_id`
- [ ] The Delete link and button use CSS variables only (no hardcoded hex)
- [ ] `test_delete_stub_unchanged` is removed and `CLAUDE.md` route table and helper list are updated
- [ ] `pytest` passes, including the new `tests/test_delete_expense.py`
