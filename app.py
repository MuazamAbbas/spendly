import math
import re
from datetime import date

from flask import Flask, render_template, redirect, request, session, url_for, abort
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    create_expense,
    get_expense_by_id,
    update_expense,
    delete_expense as db_delete_expense,
)

app = Flask(__name__)
# Hardcoded for teaching/demo purposes only — use an environment variable in production.
app.secret_key = "dev-secret-key-change-in-production"

with app.app_context():
    init_db()
    seed_db()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def _initials(name):
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _build_trend(trend_data):
    max_amount = max(entry["amount"] for entry in trend_data)
    return [
        {
            "month": entry["month"],
            "amount": entry["amount"],
            "percent": round(entry["amount"] / max_amount * 100),
        }
        for entry in trend_data
    ]


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


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    stats = {
        "total_spent": 342.75,
        "avg_transaction": 42.84,
        "transaction_count": 8,
    }

    trend_data = [
        {"month": "Feb", "amount": 210.00},
        {"month": "Mar", "amount": 265.50},
        {"month": "Apr", "amount": 180.25},
        {"month": "May", "amount": 310.00},
        {"month": "Jun", "amount": 295.75},
        {"month": "Jul", "amount": 342.75},
    ]
    trend = _build_trend(trend_data)

    categories = [
        {"name": "Food", "total": 120.50, "percent": 35},
        {"name": "Bills", "total": 95.00, "percent": 28},
        {"name": "Transport", "total": 68.25, "percent": 20},
        {"name": "Entertainment", "total": 59.00, "percent": 17},
    ]

    top_expenses = [
        {
            "date": "2026-07-05",
            "description": "Internet bill",
            "category": "Bills",
            "amount": 120.00,
        },
        {
            "date": "2026-07-12",
            "description": "Clothing",
            "category": "Shopping",
            "amount": 89.99,
        },
        {
            "date": "2026-07-01",
            "description": "Grocery shopping",
            "category": "Food",
            "amount": 45.50,
        },
    ]

    return render_template(
        "analytics.html",
        stats=stats,
        trend=trend,
        categories=categories,
        top_expenses=top_expenses,
    )


def _validate_expense_form(form):
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    description = form.get("description", "").strip()
    form_values = {"amount": amount_raw, "category": category, "date": date_raw, "description": description}

    try:
        amount = float(amount_raw)
    except ValueError:
        return form_values, None, "Enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return form_values, None, "Amount must be greater than zero."

    if category not in EXPENSE_CATEGORIES:
        return form_values, None, "Select a valid category."

    try:
        date.fromisoformat(date_raw)
    except ValueError:
        return form_values, None, "Enter a valid date."

    return form_values, amount, None


def _render_add_expense_error(message, form_values):
    return render_template("add_expense.html", categories=EXPENSE_CATEGORIES,
                            error=message, **form_values), 400


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("add_expense.html", categories=EXPENSE_CATEGORIES)

    form_values, amount, error = _validate_expense_form(request.form)
    if error:
        return _render_add_expense_error(error, form_values)

    create_expense(session["user_id"], amount, form_values["category"],
                    form_values["date"], form_values["description"] or None)
    return redirect(url_for("profile"))


def _render_edit_expense_error(expense_id, message, form_values):
    return render_template("edit_expense.html", categories=EXPENSE_CATEGORIES,
                            expense_id=expense_id, error=message, **form_values), 400


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template("edit_expense.html", categories=EXPENSE_CATEGORIES,
                                expense_id=expense["id"], amount=expense["amount"],
                                category=expense["category"], date=expense["date"],
                                description=expense["description"])

    form_values, amount, error = _validate_expense_form(request.form)
    if error:
        return _render_edit_expense_error(id, error, form_values)

    update_expense(id, session["user_id"], amount, form_values["category"],
                    form_values["date"], form_values["description"] or None)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    db_delete_expense(id, session["user_id"])
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
