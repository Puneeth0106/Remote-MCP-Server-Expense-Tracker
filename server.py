import os
import time
import psycopg2 #PostgreSQL database adapter for Python
from psycopg2.extras import RealDictCursor # For returning a python dictionary
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token

load_dotenv()  # Load environment variables from .env file

DB_URL= os.getenv("DATABASE_URL")
CATEGORIES_PATH= os.path.join(os.path.dirname(__file__),"categories.json")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
JWT_KEY = os.getenv("JWT_SIGNING_KEY")

# 1. SetUp Authentication
auth_provider = GitHubProvider(
    client_id=GITHUB_CLIENT_ID,
    client_secret= GITHUB_CLIENT_SECRET,
    base_url=BASE_URL,
    jwt_signing_key= JWT_KEY)


mcp= FastMCP("Cloud-Expense-Tracker", auth=auth_provider)


# 2. Database Connection
def get_db_connection():
    """ Establish connection to the Cloud postgres DB(Supabase)"""
    conn= psycopg2.connect(DB_URL, cursor_factory= RealDictCursor )
    return conn


# 3. Tools With Data Governance

## Tool-1: Adding expense according to the user
@mcp.tool()
def add_expense(date, amount: float, category : str, subcategory='',note=''):
    """Add a new expense. Automatically linked to your secure GitHub identity."""
    # SECURITY: Get the user identity from the token
    try:
        token= get_access_token()
        current_user= token.claims.get("login")
    except Exception:
        raise "Error: Your not logged in. Please Authenticate"
    
    # DATABASE : Insert with Strict user_id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (user_id, date, amount, category, subcategory, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (current_user,date,amount,category,subcategory,note)
                )
                new_id= cur.fetchone()['id']
                conn.commit()
                return f'Expense added successfully. ID : {new_id}'
    except Exception as e:
        return f"Database error: {str(e)}"

## Tool-2: List expenses of the user
@mcp.tool()
def list_expenses(start_date: str, end_date: str):
    """ List only your expense"""

    # SECURITY: Get the user identity from the token
    try:
        token= get_access_token()
        current_user= token.claims.get("login")
    except Exception:
        raise "Error: Your not logged in. Please Authenticate"


    # DATA GOVERNANCE: Row-Level Security
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select * from expenses
                    where user_id= %s and
                    date between %s and %s
                    order by date asc
                    """,
                    (current_user,start_date,end_date)
                )
                rows= cur.fetchall()
                if not rows:
                    return f"No expenses found for user {current_user}."
                return str(rows)
    except Exception as e:
        return f"Database error: {str(e)}"



### Tool-3: Summarize expenses of the user
@mcp.tool()
def summarize_expenses(start_date: str, end_date: str, category: str = None):
    """ Summarize your expenses with optional category filter"""

    # SECURITY: Get the user identity from the token
    try:
        token= get_access_token()
        current_user= token.claims.get("login")
    except Exception:
        raise "Error: Your not logged in. Please Authenticate"
    
    # DATA GOVERNANCE: Row-Level Security with optional category filter
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query= """
                    select category, sum(amount) as total_amount
                    from expenses
                    where user_id= %s and date between %s and %s
                """
                parameters= [current_user, start_date, end_date]
                if category:
                    query += " and category= %s"
                    parameters.append(category)
                query += " group by category order by category asc"
                
                cur.execute(query, parameters)
                rows= cur.fetchall()
                if not rows:
                    return f"No expenses found for user {current_user}."
                return str(rows)
    except Exception as e:
        return f"Database error: {str(e)}"
    

### Tool-4: Delete expense of the user
@mcp.tool()
def delete_expense(expense_id: int):
    """ Delete your expense by ID """
    # SECURITY: Get the user identity from the token
    try:
        token= get_access_token()
        current_user= token.claims.get("login")
    except Exception:
        raise "Error: Your not logged in. Please Authenticate"
    

    # DATA GOVERNANCE: Row-Level Security on Delete
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM expenses
                    WHERE id= %s AND user_id= %s
                    """,
                    (expense_id, current_user)
                )
                if cur.rowcount==0:
                    return f"Expense ID {expense_id} not found for user {current_user}."
                conn.commit()
                return f"Expense ID {expense_id} deleted successfully."
    except Exception as e:
        return f"Database error: {str(e)}"
    

## Tool-5: Upload Expense Categories Resource
@mcp.tool()
def update_expense(expense_id: int, date=None, amount: float = None, category: str = None, subcategory: str = None, note: str = None):
    """ Update your expense by ID with provided fields """
    # SECURITY: Get the user identity from the token
    try:
        token= get_access_token()
        current_user= token.claims.get("login")
    except Exception:
        raise "Error: Your not logged in. Please Authenticate"
    # DATA GOVERNANCE: Row-Level Security on Update
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                fields_to_update= []
                params= []

                if date is not None:
                    fields_to_update.append("date = %s")
                    params.append(date)
                if amount is not None:
                    fields_to_update.append("amount = %s")
                    params.append(amount)
                if category is not None:
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

                query= f"""
                    UPDATE expenses
                    SET {', '.join(fields_to_update)}
                    WHERE id= %s AND user_id= %s
                """
                params.extend([expense_id, current_user])

                cur.execute(query, params)
                if cur.rowcount==0:
                    return f"Expense ID {expense_id} not found for user {current_user}."
                conn.commit()
                return f"Expense ID {expense_id} updated successfully."
    except Exception as e:
        return f"Database error: {str(e)}"
    

@mcp.resource("expense://categories",mime_type="application/json")
# expense://categories - MCP URI, mime_type="application/json" - Tells AI about what type of content you can expect
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, 'r') as f:
        return f.read()


if __name__=="__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
