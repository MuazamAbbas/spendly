from datetime import datetime

from database.db import get_db


# ------------------------------------------------------------------ #
# User info                                                           #
# ------------------------------------------------------------------ #

def _format_member_since(created_at):
    dt = datetime.strptime(created_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%B %Y")


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

def get_summary_stats(user_id):
    conn = get_db()
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total_spent, "
        "COUNT(*) AS transaction_count FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    top = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
        (user_id,),
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

def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, limit),
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

def get_category_breakdown(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS cat_total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY cat_total DESC, category ASC",
        (user_id,),
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
