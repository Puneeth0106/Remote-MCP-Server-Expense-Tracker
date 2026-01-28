from fastmcp import FastMCP
import os
import sqlite3
from typing import Optional

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
async def add_expense(date, amount, category, subcategory='',note=''):
    """ Add a new expense to the database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor= conn.cursor()
        cursor.execute(
            "Insert into expenses(date,amount, category, subcategory,note) values(?,?,?,?,?)",
            (date, amount, category, subcategory,note))
        await conn.commit()
        return {'status':'ok','id':cursor.lastrowid}



#List Expenses Tool
@mcp.tool()
async def list_expenses(start_date, end_date):
    """ List Expense within the inclusive Data Range """
    with sqlite3.connect(DB_PATH) as conn:
        cursor= conn.cursor()
        cursor.execute(
            """
                Select * from expenses
                where date between ? and ?
            """,
            (start_date,end_date)
        )
        #cur.description contains metadata: Columns
        cols= [d[0] for d in cursor.description]
        #Zip and Convert: [('id', 1), ('date', '2025-01-01'), ('amount', 50.00)...]
        return [dict(zip(cols,r)) for r in cursor.fetchall()]
    

#Summarize based on category if included
@mcp.tool()
async def summarize_expenses(start_date,end_date,category=None):
    """Summarize Expenses within the inclusive range and also summarize based on category if provided"""
    with sqlite3.connect(DB_PATH) as conn:
        query=  ("""
        Select category,sum(amount) from expenses
        where date between  ? and ?
        """)
        parameters= [start_date,end_date]
        if category:
            query += "and category= ?"
            parameters.append(category)
        
        query += "Group by category order by category asc"

        cursor= conn.cursor()
        cursor.execute(
            query,
            parameters
        )
        cols= [d[0] for d in conn.description]
        return [dict(zip(cols,r)) for r in cursor.fetchall()]

@mcp.tool()
async def delete_expense(id:int):
    """ Delete expense from expenses table with given expense id """
    with sqlite3.connect(DB_PATH) as conn:
        cursor= conn.cursor()
        cursor.execute(
            """
            Delete from expenses 
            where id= ?
            """,
            (id,) #Single item tuple
        )
        #Use rowcount for UPDATE and DELETE to verify changes happened.
        if cursor.rowcount==0:
            return{'status':'error', 'message':f'Expense ID {id} not found'}
        return {'status':'ok','message':f'Expense {id} deleted successfully'}
    
@mcp.tool()
async def update_expense(id:int,date:Optional[str] =None, amount:Optional[float] =None, category:Optional[str] =None, subcategory:Optional[str] =None ,note:Optional[str]=None):
    """Update the expense with provided column values using the id provided """
    with sqlite3.connect(DB_PATH) as conn:
        fields_to_update= []
        params=[]

        # 1. Collect the fields that need updating
        if date is not None:
            fields_to_update.append("date = ?")
            params.append(date)
        if amount is not None:
            fields_to_update.append("amount = ?")
            params.append(amount)
        if category is not None:
            fields_to_update.append("category = ?")
            params.append(category)
        if subcategory is not None:
            fields_to_update.append("subcategory = ?")
            params.append(subcategory)
        if note is not None:
            fields_to_update.append("note = ?")
            params.append(note)
        
        await conn.commit()
        # 2. Safety check: Did the user actually provide anything to update?
        if len(fields_to_update)==0:
            return{'status':'error', 'message':'No fields provided to update'}
        
        # 3. Build the dynamic SQL query
        query= f""" Update expenses
                Set {','.join(fields_to_update)}
                Where id = ? """
        
        params.append(id)

        cursor= conn.cursor()
        cursor.execute(
            query,
            params
        )
        #Use rowcount for UPDATE and DELETE to verify changes happened.
        if cursor.rowcount==0:
            return {'status':'error', 'message':f'Expenses with id {id} is not found'}
        return {'status':'ok', 'message':f'Expenses with id {id} is Updated'}



@mcp.resource("expense://categories",mime_type="application/json")
# expense://categories - MCP URI, mime_type="application/json" - Tells AI about what type of content you can expect
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, 'r') as f:
        return f.read()

            


if __name__ == "__main__":
    mcp.run(transport='http',host= '0.0.0.0', port=8000)          
            
            

        
