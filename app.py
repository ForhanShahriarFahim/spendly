import calendar
import os
import sqlite3
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    delete_expense as db_delete_expense,
    get_category_breakdown,
    get_db,
    get_expense,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    get_user_profile,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
# Development-only fallback; set SECRET_KEY in the environment for real use.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")


def _current_user():
    """Return the logged-in user row, or None. A session whose user no
    longer exists is cleared. Not cached on g: the app context can outlive
    a single request (e.g. under pytest-flask), which would serve stale data."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
    return user


@app.context_processor
def inject_current_user():
    return {"current_user": _current_user()}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    return render_template("landing.html")


def _render_register_error(message, name, email):
    return render_template("register.html", error=message, name=name, email=email), 200


@app.route("/register", methods=["GET", "POST"])
def register():
    if _current_user():
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name:
        return _render_register_error("Please enter your full name.", name, email)
    if not email:
        return _render_register_error("Please enter your email address.", name, email)
    if "@" not in email:
        return _render_register_error(
            "Please enter a valid email address.", name, email
        )
    if len(password) < 8:
        return _render_register_error(
            "Password must be at least 8 characters.", name, email
        )
    duplicate_error = "An account with this email already exists."
    if get_user_by_email(email):
        return _render_register_error(duplicate_error, name, email)

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        return _render_register_error(duplicate_error, name, email)

    return redirect(url_for("login", registered=1))


def _render_login_error(message, email):
    return render_template("login.html", error=message, email=email), 200


@app.route("/login", methods=["GET", "POST"])
def login():
    if _current_user():
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template(
            "login.html", registered=request.args.get("registered") == "1"
        )

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email:
        return _render_login_error("Please enter your email address.", email)
    if not password:
        return _render_login_error("Please enter your password.", email)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return _render_login_error("Invalid email or password.", email)

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _parse_iso_date(value):
    """Return `value` as a normalised YYYY-MM-DD string, or None if it is
    missing or malformed (a bad value is treated as absent)."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


MAX_EXPENSE_AMOUNT = Decimal("9999999.99")
MAX_DESCRIPTION_LENGTH = 200


def _parse_amount(raw):
    """Return `raw` as a positive 2dp float, or None if it is not a finite
    number in (0, MAX_EXPENSE_AMOUNT]. A float is fine: the amount column is
    REAL."""
    try:
        amount = Decimal(raw.strip())
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_EXPENSE_AMOUNT:
        return None
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # A value like 0.001 rounds down to zero.
    return float(amount) if amount > 0 else None


def _validate_expense_form(form):
    """Return (cleaned, error). `cleaned` holds amount, category, date and
    description when valid; otherwise it is None and `error` explains why.
    A blank description is left as "" (create_expense stores it as NULL)."""
    amount = _parse_amount(form.get("amount", ""))
    if amount is None:
        return None, "Please enter an amount greater than zero."

    category = form.get("category", "")
    if category not in CATEGORIES:
        return None, "Please choose a valid category."

    date_str = _parse_iso_date(form.get("date", ""))
    if date_str is None:
        return None, "Please enter a valid date."

    description = form.get("description", "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return None, (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )

    return {
        "amount": amount,
        "category": category,
        "date": date_str,
        "description": description,
    }, None


def _render_add_expense(form, error=None):
    return (
        render_template(
            "add_expense.html",
            error=error,
            form=form,
            categories=CATEGORIES,
            max_description_length=MAX_DESCRIPTION_LENGTH,
        ),
        200,
    )


def _render_edit_expense(expense_id, form, error=None):
    return (
        render_template(
            "edit_expense.html",
            error=error,
            form=form,
            expense_id=expense_id,
            categories=CATEGORIES,
            max_description_length=MAX_DESCRIPTION_LENGTH,
        ),
        200,
    )


def _shift_months(day, months):
    """Move `day` by a number of months, clamping to the month's last day."""
    # Months since year 0 as a single integer, so divmod handles year rollover.
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last_day))


def _filter_presets(today):
    """Quick-select date ranges as dicts of label, date_from and date_to."""
    today_iso = today.isoformat()
    return [
        {
            "label": "This Month",
            "date_from": today.replace(day=1).isoformat(),
            "date_to": today_iso,
        },
        {
            "label": "Last 3 Months",
            "date_from": _shift_months(today, -3).isoformat(),
            "date_to": today_iso,
        },
        {
            "label": "Last 6 Months",
            "date_from": _shift_months(today, -6).isoformat(),
            "date_to": today_iso,
        },
        {"label": "All Time", "date_from": None, "date_to": None},
    ]


def _resolve_date_filter(args, today):
    """Validate date_from/date_to from the query string. Returns a dict with
    date_from, date_to, error, presets (each flagged `active`) and
    custom_active. A malformed value is ignored; a reversed range is dropped
    with an error message."""
    date_from = _parse_iso_date(args.get("date_from"))
    date_to = _parse_iso_date(args.get("date_to"))
    error = None
    if date_from and date_to and date_from > date_to:
        date_from = date_to = None
        error = "Start date must be before end date."

    presets = _filter_presets(today)
    for preset in presets:
        preset["active"] = (
            preset["date_from"] == date_from and preset["date_to"] == date_to
        )
    custom_active = bool(date_from or date_to) and not any(p["active"] for p in presets)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "error": error,
        "presets": presets,
        "custom_active": custom_active,
    }


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    user = get_user_profile(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    date_filter = _resolve_date_filter(request.args, date.today())
    date_from = date_filter["date_from"]
    date_to = date_filter["date_to"]

    summary = get_expense_summary(user_id, date_from, date_to)
    breakdown = get_category_breakdown(user_id, date_from, date_to)
    has_expenses = summary["count"] > 0
    if not has_expenses and (date_from or date_to):
        # An empty filtered range: tell "no expenses at all" from "none here".
        has_expenses = get_expense_summary(user_id)["count"] > 0
    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        breakdown=breakdown,
        top_category=breakdown[0] if breakdown else None,
        recent=get_recent_expenses(user_id, date_from=date_from, date_to=date_to),
        date_from=date_from,
        date_to=date_to,
        has_expenses=has_expenses,
        filter_error=date_filter["error"],
        presets=date_filter["presets"],
        custom_active=date_filter["custom_active"],
    )


@app.route("/analytics")
def analytics():
    if _current_user() is None:
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if _current_user() is None:
        return redirect(url_for("login"))

    if request.method == "GET":
        return _render_add_expense({"date": date.today().isoformat()})

    cleaned, error = _validate_expense_form(request.form)
    if error:
        return _render_add_expense(request.form, error)

    create_expense(
        session["user_id"],
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if _current_user() is None:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        form = dict(expense)
        form["amount"] = f"{form['amount']:.2f}"
        form["description"] = form["description"] or ""
        return _render_edit_expense(id, form)

    cleaned, error = _validate_expense_form(request.form)
    if error:
        return _render_edit_expense(id, request.form, error)

    if not update_expense(
        id,
        user_id,
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    ):
        abort(404)
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense(id):
    if _current_user() is None:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    expense = get_expense(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template("delete_expense.html", expense=expense)

    if not db_delete_expense(id, user_id):
        abort(404)
    return redirect(url_for("profile"))


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
