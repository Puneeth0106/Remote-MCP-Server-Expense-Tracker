import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastmcp import FastMCP
from contextlib import contextmanager


#Embedding Categories
Categories= {
  "food": [
    "groceries",
    "fruits_vegetables",
    "dairy_bakery",
    "dining_out",
    "coffee_tea",
    "snacks",
    "delivery_fees",
    "other"
  ],
  "transport": [
    "fuel",
    "public_transport",
    "cab_ride_hailing",
    "parking",
    "tolls",
    "vehicle_service",
    "other"
  ],
  "housing": [
    "rent",
    "maintenance_hoa",
    "property_tax",
    "repairs_service",
    "cleaning",
    "furnishing",
    "other"
  ],
  "utilities": [
    "electricity",
    "water",
    "gas",
    "internet_broadband",
    "mobile_phone",
    "tv_dth",
    "other"
  ],
  "health": [
    "medicines",
    "doctor_consultation",
    "diagnostics_labs",
    "insurance_health",
    "fitness_gym",
    "other"
  ],
  "education": [
    "books",
    "courses",
    "online_subscriptions",
    "exam_fees",
    "workshops",
    "other"
  ],
  "family_kids": [
    "school_fees",
    "daycare",
    "toys_games",
    "clothes",
    "events_birthdays",
    "other"
  ],
  "entertainment": [
    "movies_events",
    "streaming_subscriptions",
    "games_apps",
    "outing",
    "other"
  ],
  "shopping": [
    "clothing",
    "footwear",
    "accessories",
    "electronics_gadgets",
    "appliances",
    "home_decor",
    "other"
  ],
  "subscriptions": [
    "saas_tools",
    "cloud_ai",
    "newsletters",
    "music_video",
    "storage_backup",
    "other"
  ],
  "personal_care": [
    "salon_spa",
    "grooming",
    "cosmetics",
    "hygiene",
    "other"
  ],
  "gifts_donations": [
    "gifts_personal",
    "charity_donation",
    "festivals",
    "other"
  ],
  "finance_fees": [
    "bank_charges",
    "late_fees",
    "interest",
    "brokerage",
    "other"
  ],
  "business": [
    "software_tools",
    "hosting_domains",
    "marketing_ads",
    "contractor_payments",
    "travel_business",
    "office_supplies",
    "other"
  ],
  "travel": [
    "flights",
    "hotels",
    "train_bus",
    "visa_passport",
    "local_transport",
    "food_travel",
    "other"
  ],
  "home": [
    "household_supplies",
    "cleaning_supplies",
    "kitchenware",
    "small_repairs",
    "pest_control",
    "other"
  ],
  "pet": [
    "food",
    "vet",
    "grooming",
    "supplies",
    "other"
  ],
  "taxes": [
    "income_tax",
    "gst",
    "professional_tax",
    "filing_fees",
    "other"
  ],
  "investments": [
    "mutual_funds",
    "stocks",
    "fd_rd",
    "gold",
    "crypto",
    "brokerage_fees",
    "other"
  ],
  "misc": [
    "uncategorized",
    "rounding",
    "other"
  ]
}



# 1. Load Environment & Config
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("Expense-Tracker")

# Global variable to store why the connection failed
STARTUP_ERROR = None
db_pool = None

# 2. Initialize Connection Pool
try:
    raw_url = os.getenv("DATABASE_URL")
    
    # Clean and Validate URL
    if raw_url:
        DB_URL = raw_url.strip().strip("'").strip('"')
    else:
        DB_URL = None

    if not DB_URL:
        raise ValueError("DATABASE_URL environment variable is missing or empty.")

    # Force SSL for Supabase
    if "sslmode" not in DB_URL:
        separator = "&" if "?" in DB_URL else "?"
        DB_URL = f"{DB_URL}{separator}sslmode=require"

    # Create Pool (optimized for cloud deployment)
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,  # Reduced for cloud environments to avoid connection exhaustion
        dsn=DB_URL,
        cursor_factory=RealDictCursor
    )
    print("Database pool initialized successfully.")

except Exception as e:
    # CAPTURE the specific error so we can show it to the user
    STARTUP_ERROR = f"Startup Failed: {str(e)}"
    print(STARTUP_ERROR) # Print to logs too
    db_pool = None

@contextmanager
def get_db_connection():
    """
    Context manager to get a connection from the pool and return it safely.
    """
    # 1. Check if we have a specific startup error to report
    if STARTUP_ERROR:
        raise Exception(f"DATABASE ERROR: {STARTUP_ERROR}")

    # 2. Check if pool is missing for unknown reasons
    if not db_pool:
        raise Exception("Database pool is not initialized (Unknown Reason).")
    
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

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

    # 1. Check Identity
    identity_error = ensure_user_identity(user_id)
    if identity_error:
        return identity_error  
    
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

    # 1. Check Identity
    identity_error = ensure_user_identity(user_id)
    if identity_error:
        return identity_error
    
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
    # 1. Check Identity
    identity_error = ensure_user_identity(user_id)
    if identity_error:
        return identity_error
    
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
    # 1. Check Identity
    identity_error = ensure_user_identity(user_id)
    if identity_error:
        return identity_error
    
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
    # 1. Check Identity
    identity_error = ensure_user_identity(user_id)
    if identity_error:
        return identity_error
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
    """Resource: Expense Categories (embedded for cloud deployment)"""
    import json
    return json.dumps(Categories, indent=2)

# For local development only
if __name__ == "__main__":
    # FastMCP cloud will handle server configuration automatically
    # This block is only for local testing
    try:
        mcp.run()
    finally:
        if db_pool:
            db_pool.closeall()