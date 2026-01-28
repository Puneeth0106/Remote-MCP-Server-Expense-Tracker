import asyncio
from fastmcp import Client
from fastmcp.client.auth import OAuth

async def main():

    # Use the 'oauth_config' object for the auth parameter
    async with Client("https://Remote-Expense-Tracker.fastmcp.app/mcp") as client:
        print("✓ Successfully authenticated with GitHub!")
        
        # Call your protected tool
        result = await client.call_tool("list_expenses", start_date="2024-01-01", end_date="2024-12-31")
        print(f"Server Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())