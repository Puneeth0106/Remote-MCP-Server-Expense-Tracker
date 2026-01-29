from fastmcp import FastMCP
import os
import sqlite3
from typing import Optional
import json

# Setup paths
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("Puneeth-Expense-Tracker")

def initialize_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS EXPENSES(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        conn.commit()

# Ensure categories file exists for the blog demo
if not os.path.exists(CATEGORIES_PATH):
    with open(CATEGORIES_PATH, 'w') as f:
        json.dump({"categories": ["Food", "Transport", "Rent", "Utilities"]}, f)

initialize_db()

@mcp.tool()
def add_expense(date: str, amount: float, category: str, subcategory: str = '', note: str = ''):
    """Add a new expense to the database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES(?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        conn.commit()
        return {'status': 'ok', 'id': cursor.lastrowid}

@mcp.tool()
def list_expenses(start_date: str, end_date: str):
    """List expenses within the inclusive Date Range (YYYY-MM-DD)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row # Allows dictionary-like access
        cursor = conn.execute(
            "SELECT * FROM expenses WHERE date BETWEEN ? AND ?",
            (start_date, end_date)
        )
        return [dict(row) for row in cursor.fetchall()]

@mcp.tool()
def summarize_expenses(start_date: str, end_date: str, category: Optional[str] = None):
    """Summarize expenses by category within a date range"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT category, SUM(amount) as total FROM expenses WHERE date BETWEEN ? AND ?"
        params = [start_date, end_date]
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " GROUP BY category ORDER BY total DESC"
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

@mcp.resource("expense://categories")
def get_categories() -> str:
    """Fetch the list of valid expense categories"""
    with open(CATEGORIES_PATH, 'r') as f:
        return f.read()

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.run(transport='http', host='0.0.0.0', port=8000)