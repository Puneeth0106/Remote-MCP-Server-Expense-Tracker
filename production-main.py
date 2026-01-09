import os
import requests
import time
import webbrowser #Lets your Python script talk to your computer's default web browser.
import psycopg2 #PostgreSQL database adapter for Python
from psycopg2.extras import RealDictCursor # For returning a python dictionary
from dotenv import load_dotenv
from fastmcp import FastMCP

# 1. Load Secrets
load_dotenv()
DB_URL= os.getenv("DATABASE_URL")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")

if not DB_URL:
    raise ValueError("Database URL is missing from .env file")

print("Hi! Witness my first production ready mcp server!")

mcp= FastMCP("Cloud-Expense-Tracker")

# GLOBAL AUTHENTICATION STATE
CURRENT_USER= None

# DATABASE HELPER (Context Manager)

def get_db_connection():
    """ Establish connection to the Cloud postgres DB(Supabase)"""
    conn= psycopg2.connect(DB_URL, cursor_factory= RealDictCursor )
    return conn

# AUTHENTICATION FLOW (Device Flow) 

def login_with_github():
    """
    Performs the OAuth Device Flow.
    Returns the username (login) of the authenticated user
    """
    print("\n--- 🔐 Initiating Secure Login ---")
    
    # Step A: Get Device Code

