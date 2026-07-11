import re
from datetime import date

from flask import Flask, render_template, redirect, request, session, url_for
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
# Hardcoded for teaching/demo purposes only — use an environment variable in production.
app.secret_key = "dev-secret-key-change-in-production"

with app.app_context():
    init_db()
    seed_db()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _initials(name):
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _parse_date_filter(args):
    start_raw = args.get("start_date", "").strip()
    end_raw = args.get("end_date", "").strip()

    if not start_raw or not end_raw:
        return None, None

    try:
        start_dt = date.fromisoformat(start_raw)
        end_dt = date.fromisoformat(end_raw)
    except ValueError:
        return None, None

    if start_dt > end_dt:
        start_raw, end_raw = end_raw, start_raw

    return start_raw, end_raw


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "")
    email = request.form.get("email", "")
    password = request.form.get("password", "")

    name_clean = name.strip()
    email_clean = email.strip().lower()

    if not name_clean:
        return render_template("register.html", error="Full name is required."), 400

    if not EMAIL_RE.match(email_clean):
        return render_template("register.html", error="Enter a valid email address."), 400

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters."), 400

    if get_user_by_email(email_clean):
        return render_template("register.html", error="An account with that email already exists."), 400

    user_id = create_user(name_clean, email_clean, password)
    session["user_id"] = user_id
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "")
    password = request.form.get("password", "")
    email_clean = email.strip().lower()

    user = get_user_by_email(email_clean)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password."), 400

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    start_date, end_date = _parse_date_filter(request.args)

    # ---------------------------------------------------------------- #
    # USER INFO — get_user_by_id                                        #
    # ---------------------------------------------------------------- #
    profile_user = get_user_by_id(user_id)
    user = {
        "name": profile_user["name"],
        "email": profile_user["email"],
        "initials": _initials(profile_user["name"]),
        "member_since": profile_user["member_since"],
    }

    # ---------------------------------------------------------------- #
    # SUBAGENT-2: summary stats                                         #
    # ---------------------------------------------------------------- #
    stats = get_summary_stats(user_id, start_date=start_date, end_date=end_date)

    # ---------------------------------------------------------------- #
    # SUBAGENT-1: transaction history                                   #
    # ---------------------------------------------------------------- #
    transactions = get_recent_transactions(user_id, start_date=start_date, end_date=end_date)

    # ---------------------------------------------------------------- #
    # SUBAGENT-3: category breakdown                                    #
    # ---------------------------------------------------------------- #
    breakdown = get_category_breakdown(user_id, start_date=start_date, end_date=end_date)
    categories = [
        {"name": c["name"], "total": c["amount"], "percent": c["pct"]}
        for c in breakdown
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
