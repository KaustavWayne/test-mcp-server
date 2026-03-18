from fastmcp import FastMCP
import os
import aiosqlite
import tempfile
import json

TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

print(f"Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")


# Keep initialization synchronous
def init_db():
    import sqlite3
    with sqlite3.connect(DB_PATH) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

init_db()


@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense entry."""

    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            await c.commit()

            return {
                "status": "ok",
                "id": cur.lastrowid
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def edit_expense(id, date=None, amount=None, category=None, subcategory=None, note=None):
    """Edit an existing expense entry."""

    updates = []
    params = []

    if date is not None:
        updates.append("date=?")
        params.append(date)

    if amount is not None:
        updates.append("amount=?")
        params.append(amount)

    if category is not None:
        updates.append("category=?")
        params.append(category)

    if subcategory is not None:
        updates.append("subcategory=?")
        params.append(subcategory)

    if note is not None:
        updates.append("note=?")
        params.append(note)

    if not updates:
        return {"status": "error", "message": "No fields provided"}

    params.append(id)

    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                f"UPDATE expenses SET {', '.join(updates)} WHERE id=?",
                params
            )

            await c.commit()

            if cur.rowcount == 0:
                return {"status": "error", "message": "Expense not found"}

        return {"status": "ok", "updated_id": id}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def delete_expense(id):
    """Delete an expense entry."""

    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "DELETE FROM expenses WHERE id=?",
                (id,)
            )

            await c.commit()

            if cur.rowcount == 0:
                return {"status": "error", "message": "Expense not found"}

        return {"status": "ok", "deleted_id": id}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expenses within date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
                """,
                (start_date, end_date)
            )

            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]

            return [dict(zip(cols, r)) for r in rows]

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses by category."""

    query = """
        SELECT category, SUM(amount) as total_amount, COUNT(*) as count
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """

    params = [start_date, end_date]

    if category:
        query += " AND category=?"
        params.append(category)

    query += " GROUP BY category ORDER BY total_amount DESC"

    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(query, params)

            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]

            return [dict(zip(cols, r)) for r in rows]

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    """Return categories list."""

    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return json.dumps(default_categories, indent=2)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)