import os
import sqlite3

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    get_user_profile,
    init_db,
    seed_db,
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
    return render_template(
        "register.html", error=message, name=name, email=email
    ), 200


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
        return _render_register_error(
            "Please enter your email address.", name, email)
    if "@" not in email:
        return _render_register_error(
            "Please enter a valid email address.", name, email)
    if len(password) < 8:
        return _render_register_error(
            "Password must be at least 8 characters.", name, email)
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


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    user = get_user_profile(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    breakdown = get_category_breakdown(user_id)
    return render_template(
        "profile.html",
        user=user,
        summary=get_expense_summary(user_id),
        breakdown=breakdown,
        top_category=breakdown[0] if breakdown else None,
        recent=get_recent_expenses(user_id),
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
