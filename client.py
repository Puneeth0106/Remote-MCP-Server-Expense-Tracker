import asyncio
from fastmcp import Client
from fastmcp.client.auth import OAuth

async def main():
    # We use 'mcp_url' to tell the client where to find the server metadata
    # We use 'callback_port' to keep things consistent
    oauth_config = OAuth(
        mcp_url="http://localhost:8000/mcp",
        # This matches the /callback path we just put in GitHub
    )

    # Use the 'oauth_config' object for the auth parameter
    async with Client("http://localhost:8000/mcp", auth=oauth_config) as client:
        print("✓ Successfully authenticated with GitHub!")
        
        # Call your protected tool
        result = await client.call_tool("who_am_i")
        print(f"Server Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())