import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastmcp import FastMCP
from contextlib import contextmanager



# 1. Load Environment & Config
load_dotenv()

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "resources/categories.json")

# Initialize FastMCP
mcp = FastMCP("Expense-Tracker")


# 2. Initialize Connection Pool (Production Ready)
try:
    # A. Get the raw variable
    raw_url = os.getenv("DATABASE_URL")
    
    # B. CLEAN IT: Remove whitespace and quotes (Standardize the string)
    if raw_url:
        DB_URL = raw_url.strip().strip("'").strip('"')
    else:
        DB_URL = None

    # C. FORCE SSL: Supabase REQUIRES this. 
    # If we don't add it, the connection drops silently (Empty OperationalError).
    if DB_URL and "sslmode" not in DB_URL:
        # Check if URL already has query parameters (?)
        separator = "&" if "?" in DB_URL else "?"
        DB_URL = f"{DB_URL}{separator}sslmode=require"

    # D. Create the Pool
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=DB_URL,
        cursor_factory=RealDictCursor
    )
    print("Database pool initialized successfully with SSL.")

except Exception as e:
    # If it still fails, print the modified URL (masked) to see if SSL was added
    masked_url = DB_URL.replace(DB_URL.split(':')[2].split('@')[0], '******') if DB_URL and '@' in DB_URL else "INVALID_URL"
    print(f"Startup Failed. Final URL used: {masked_url}")
    print(f"Error: {e}")
    db_pool = None

# 3. Helper to get user and handle errors centrally
def ensure_user_identity(user_id):
    """
    Checks if the user is 'guest'. If so, returns an error message
    that forces Claude to ask the user for their name.
    """
    if not user_id or user_id.lower() == 'guest':
        # This specific string tells the LLM what to do next
        return "IDENTITY_ERROR: I do not know the user's name yet. Please ask the user: 'What is your name?' and then try again with their answer."
    return None

## Tool-1: Adding expense
@mcp.tool()
def add_expense(date: str, amount: float, category: str, subcategory: str = '', note: str = '', user_id: str = 'guest'):
    """Add a new expense. User ID defaults to guest."""
    identity_error = ensure_user_identity(user_id)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (user_id, date, amount, category, subcategory, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, date, amount, category, subcategory, note)
                )
                new_id = cur.fetchone()['id']
                conn.commit()
                return f'Expense added successfully. ID: {new_id}'
    except Exception as e:
        return f"Database error: {str(e)}"

## Tool-2: List expenses
@mcp.tool()
def list_expenses(start_date: str, end_date: str, user_id: str = 'guest'):
    """List expenses for a specific date range."""
    identity_error = ensure_user_identity(user_id)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM expenses
                    WHERE user_id = %s AND
                    date BETWEEN %s AND %s
                    ORDER BY date ASC
                    """,
                    (user_id, start_date, end_date)
                )
                rows = cur.fetchall()
                # Return empty list description instead of None to help LLM
                if not rows:
                    return f"No expenses found for user {user_id} between {start_date} and {end_date}."
                return str(rows)
    except Exception as e:
        return f"Database error: {str(e)}"

### Tool-3: Summarize expenses
@mcp.tool()
def summarize_expenses(start_date: str, end_date: str, category: str | None = None, user_id: str = 'guest'):
    """
    Summarize expenses with optional category filter.
    """
    identity_error = ensure_user_identity(user_id)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT category, SUM(amount) as total_amount
                    FROM expenses
                    WHERE user_id = %s AND date BETWEEN %s AND %s
                """
                parameters = [user_id, start_date, end_date]
                
                # Only filter by category if one is actually provided
                if category:
                    query += " AND category = %s"
                    parameters.append(category)
                
                query += " GROUP BY category ORDER BY category ASC"
                
                cur.execute(query, parameters)
                rows = cur.fetchall()
                if not rows:
                    return f"No expenses found for user {user_id}."
                return str(rows)
    except Exception as e:
        return f"Database error: {str(e)}"

### Tool-4: Delete expense
@mcp.tool()
def delete_expense(expense_id: int, user_id: str = 'guest'):
    """Delete an expense by ID."""
    identity_error = ensure_user_identity(user_id)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM expenses WHERE id = %s AND user_id = %s",
                    (expense_id, user_id)
                )
                if cur.rowcount == 0:
                    return f"Expense ID {expense_id} not found for user {user_id}."
                conn.commit()
                return f"Expense ID {expense_id} deleted successfully."
    except Exception as e:
        return f"Database error: {str(e)}"

## Tool-5: Update Expense
def clean_input(value):
    """
    Helper: Removes extra quotes and spaces that might confuse the database.
    Example: "'2026-01-01'" -> "2026-01-01"
    """
    if isinstance(value, str):
        return value.strip().strip("'").strip('"')
    return value

@mcp.tool()
def update_expense(
    expense_id: int, 
    date: str | int | None = None,     # Allow int so we can catch it gracefully
    amount: float | None = None, 
    category: str | None = None, 
    subcategory: str | None = None, 
    note: str | None = None, 
    user_id: str = 'guest'
):
    """
    Update an expense by ID.
    Only fields that are provided will be updated.
    """
    identity_error = ensure_user_identity(user_id)
    try:
        # 1. Clean up inputs (remove accidentally added quotes)
        date = clean_input(date)
        category = clean_input(category)
        subcategory = clean_input(subcategory)
        note = clean_input(note)

        # 2. VALIDATION: Check if Date is a number (e.g. 2026) instead of a string
        if isinstance(date, int) or (isinstance(date, str) and date.isdigit()):
            return f"Error: Invalid date format '{date}'. Please use YYYY-MM-DD (e.g., '2026-01-01')."

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                fields_to_update = []
                params = []

                # 3. Build the query dynamically based on what was provided
                if date:
                    fields_to_update.append("date = %s")
                    params.append(date)
                if amount is not None:
                    fields_to_update.append("amount = %s")
                    params.append(amount)
                if category:
                    fields_to_update.append("category = %s")
                    params.append(category)
                if subcategory is not None: 
                    fields_to_update.append("subcategory = %s")
                    params.append(subcategory)
                if note is not None:
                    fields_to_update.append("note = %s")
                    params.append(note)

                if not fields_to_update:
                    return "No fields provided for update."

                # 4. Final Query Construction
                query = f"""
                    UPDATE expenses
                    SET {', '.join(fields_to_update)}
                    WHERE id = %s AND user_id = %s
                """
                params.extend([expense_id, user_id])

                cur.execute(query, params)
                
                # 5. Check if we actually found the row
                if cur.rowcount == 0:
                    return f"Expense ID {expense_id} not found for user {user_id}."
                
                conn.commit()
                return f"Expense ID {expense_id} updated successfully."
                
    except Exception as e:
        return f"Database error: {str(e)}"
    

@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    """Resource: Expense Categories"""
    if not os.path.exists(CATEGORIES_PATH):
        return '{"error": "Categories file not found", "path": "' + CATEGORIES_PATH + '"}'
        
    with open(CATEGORIES_PATH, 'r') as f:
        return f.read()

if __name__ == "__main__":
    # Ensure pool is closed on exit (optional but good practice)
    try:
        mcp.run(transport="http", port=8000, host="0.0.0.0")
    finally:
        if db_pool:
            db_pool.closeall()