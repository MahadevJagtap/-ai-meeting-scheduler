import asyncio
import psycopg
from app.config import get_settings

async def t():
    s = get_settings()
    # postgresql+asyncpg://user:pass@host:port/dbname
    conn_str = s.database_url.replace("+asyncpg", "")
    print(f"Connecting to: {conn_str}")
    try:
        async with await psycopg.AsyncConnection.connect(conn_str) as conn:
            print("✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(t())
