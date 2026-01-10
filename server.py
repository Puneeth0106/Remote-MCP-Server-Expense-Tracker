import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token
from typing import Optional

load_dotenv()

# Configuration from Environment
DB_URL = os.getenv("DATABASE_URL")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
JWT_KEY = os.getenv("JWT_SIGNING_KEY")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

# 1. Setup Authentication
auth_provider = GitHubProvider(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    base_url=BASE_URL,
    jwt_signing_key=JWT_KEY
)

mcp = FastMCP("Cloud-Expense-Tracker", auth="github")

# 2. Database Connection Helper
def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# Helper to get user and handle errors centrally
def get_current_user():
    try:
        token = get_access_token()
        return token.claims.get("login")
    except Exception:
        return None

# --- TOOLS ---

@mcp.tool()
def add_expense(date: str, amount: float, category: str, subcategory: str = '', note: str = ''):
    """Add a new expense. Automatically linked to your GitHub identity."""
    current_user = get_current_user()
    if not current_user:
        return "Error: You are not logged in. Please authenticate via the login URL."

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (user_id, date, amount, category, subcategory, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (current_user, date, amount, category, subcategory, note)
                )
                new_id = cur.fetchone()['id']
                conn.commit()
                return f'Expense added successfully. ID: {new_id}'
    except Exception as e:
        return f"Database error: {str(e)}"

@mcp.tool()
def list_expenses(start_date: str, end_date: str):
    """List only your expenses within a date range."""
    current_user = get_current_user()
    if not current_user:
        return "Error: You are not logged in."

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM expenses WHERE user_id = %s AND date BETWEEN %s AND %s ORDER BY date ASC",
                    (current_user, start_date, end_date)
                )
                rows = cur.fetchall()
                return str(rows) if rows else f"No expenses found for {current_user}."
    except Exception as e:
        return f"Database error: {str(e)}"

@mcp.tool()
def summarize_expenses(start_date: str, end_date: str, category: Optional[str] = None):
    """Summarize your expenses with optional category filter."""
    current_user = get_current_user()
    if not current_user:
        return "Error: You are not logged in."
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT category, SUM(amount) as total_amount
                    FROM expenses
                    WHERE user_id = %s AND date BETWEEN %s AND %s
                """
                params = [current_user, start_date, end_date]
                if category:
                    query += " AND category = %s"
                    params.append(category)
                query += " GROUP BY category ORDER BY category ASC"
                
                cur.execute(query, params)
                rows = cur.fetchall()
                return str(rows) if rows else "No expenses found."
    except Exception as e:
        return f"Database error: {str(e)}"

@mcp.tool()
def delete_expense(expense_id: int):
    """Delete your expense by ID."""
    current_user = get_current_user()
    if not current_user:
        return "Error: You are not logged in."

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, current_user))
                if cur.rowcount == 0:
                    return f"Expense ID {expense_id} not found or access denied."
                conn.commit()
                return f"Expense ID {expense_id} deleted successfully."
    except Exception as e:
        return f"Database error: {str(e)}"

@mcp.tool()
def update_expense(expense_id: int, date: str = None, amount: float = None, category: str = None, subcategory: str = None, note: str = None):
    """Update your expense by ID with provided fields."""
    current_user = get_current_user()
    if not current_user:
        return "Error: You are not logged in."

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                fields = []
                params = []
                if date: fields.append("date = %s"); params.append(date)
                if amount: fields.append("amount = %s"); params.append(amount)
                if category: fields.append("category = %s"); params.append(category)
                if subcategory: fields.append("subcategory = %s"); params.append(subcategory)
                if note: fields.append("note = %s"); params.append(note)

                if not fields: return "No fields provided for update."

                query = f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s AND user_id = %s"
                params.extend([expense_id, current_user])
                cur.execute(query, params)
                if cur.rowcount == 0:
                    return f"Expense ID {expense_id} not found or access denied."
                conn.commit()
                return f"Expense ID {expense_id} updated successfully."
    except Exception as e:
        return f"Database error: {str(e)}"

@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    if not os.path.exists(CATEGORIES_PATH):
        return '["Food", "Travel", "Bills", "Other"]'
    with open(CATEGORIES_PATH, 'r') as f:
        return f.read()

if __name__ == "__main__":
    mcp.run(transport="transport", host="0.0.0.0", port=8000)