from datetime import datetime

from database.db import get_db


# ------------------------------------------------------------------ #
# User info                                                           #
# ------------------------------------------------------------------ #

def _format_member_since(created_at):
    dt = datetime.strptime(created_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%B %Y")


# Returns only fixed SQL clause text — never embed request data directly
# into the returned `where` string; all values must travel via `params`.
def _build_date_where(user_id, start_date, end_date):
    where = "user_id = ?"
    params = [user_id]
    if start_date and end_date:
        where += " AND date BETWEEN ? AND ?"
        params.append(start_date)
        params.append(end_date)
    return where, tuple(params)


def create_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, (description or "")[:500] or None),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": _format_member_since(row["created_at"]),
    }


# ------------------------------------------------------------------ #
# SUBAGENT-2: summary stats                                           #
# ------------------------------------------------------------------ #

def get_summary_stats(user_id, start_date=None, end_date=None):
    conn = get_db()
    where, params = _build_date_where(user_id, start_date, end_date)

    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total_spent, "
        f"COUNT(*) AS transaction_count FROM expenses WHERE {where}",
        params,
    ).fetchone()

    top = conn.execute(
        f"SELECT category FROM expenses WHERE {where} "
        "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
        params,
    ).fetchone()
    conn.close()

    transaction_count = totals["transaction_count"]
    return {
        "total_spent": round(totals["total_spent"], 2) if transaction_count else 0,
        "transaction_count": transaction_count,
        "top_category": top["category"] if top else "—",
    }


# ------------------------------------------------------------------ #
# SUBAGENT-1: transaction history                                     #
# ------------------------------------------------------------------ #

def get_recent_transactions(user_id, limit=10, start_date=None, end_date=None):
    conn = get_db()
    where, params = _build_date_where(user_id, start_date, end_date)
    rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        f"WHERE {where} ORDER BY date DESC, id DESC LIMIT ?",
        (*params, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# ------------------------------------------------------------------ #
# SUBAGENT-3: category breakdown                                      #
# ------------------------------------------------------------------ #

def get_category_breakdown(user_id, start_date=None, end_date=None):
    conn = get_db()
    where, params = _build_date_where(user_id, start_date, end_date)
    rows = conn.execute(
        "SELECT category, SUM(amount) AS cat_total FROM expenses "
        f"WHERE {where} GROUP BY category ORDER BY cat_total DESC, category ASC",
        params,
    ).fetchall()
    conn.close()

    if not rows:
        return []

    total = sum(r["cat_total"] for r in rows)

    entries = []
    for r in rows:
        exact_pct = (r["cat_total"] / total) * 100
        floor_pct = int(exact_pct)
        entries.append(
            {
                "name": r["category"],
                "amount": round(r["cat_total"], 2),
                "pct": floor_pct,
                "_remainder": exact_pct - floor_pct,
            }
        )

    remainder = 100 - sum(e["pct"] for e in entries)
    for e in sorted(entries, key=lambda e: e["_remainder"], reverse=True)[:remainder]:
        e["pct"] += 1

    for e in entries:
        del e["_remainder"]

    return entries
