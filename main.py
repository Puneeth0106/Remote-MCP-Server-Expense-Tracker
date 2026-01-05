from fastmcp import FastMCP
import os
import sqlite3

DB_PATH= os.path.join(os.path.dirname(__file__),"expenses.db")
CATEGORIES_PATH= os.path.join(os.path.dirname(__file__),"categories.json")

mcp= FastMCP("Puneeth-Expense-Tracker")

def initialize_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor= conn.cursor()
        #Create Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS EXPENSES(
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       date TEXT NOT NULL,
                       amount REAL NOT NULL,
                       category TEXT NOT NULL,
                       subcategory TEXT DEFAULT '',
                       note TEXT DEFAULT ''
                       )
                       """)
        
initialize_db()

# Adding Tools to MCP
@mcp.tool()
def add_expense(date, amount, category, subcategory='',note=''):
    """ Add a new expense to the database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor= conn.cursor()
        cursor.execute(
            "Insert into expenses(date,amount, category, subcategory,note) values(?,?,?,?,?)",
            (date, amount, category, subcategory,note))
        return {'status':'ok','id':cursor.lastrowid}


if __name__ == "__main__":
    mcp.run()
