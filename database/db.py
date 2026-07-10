import os
import sqlite3
from werkzeug.security import generate_password_hash


def get_db():
    db_path = os.environ.get("SPENDLY_DB_PATH", "spendly.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            email        TEXT    UNIQUE NOT NULL,
            password_hash TEXT   NOT NULL,
            created_at   TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, password_hash FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    return row


def create_user(name, email, password):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name.strip(), email.strip().lower(), generate_password_hash(password)),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def seed_db():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 45.50,  "Food",          "2026-07-01", "Grocery shopping"),
        (user_id, 12.00,  "Transport",     "2026-07-03", "Uber ride"),
        (user_id, 120.00, "Bills",         "2026-07-05", "Internet bill"),
        (user_id, 35.00,  "Health",        "2026-07-08", "Pharmacy"),
        (user_id, 25.00,  "Entertainment", "2026-07-10", "Netflix subscription"),
        (user_id, 89.99,  "Shopping",      "2026-07-12", "Clothing"),
        (user_id, 15.00,  "Other",         "2026-07-15", "Miscellaneous"),
        (user_id, 32.50,  "Food",          "2026-07-18", "Restaurant dinner"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
