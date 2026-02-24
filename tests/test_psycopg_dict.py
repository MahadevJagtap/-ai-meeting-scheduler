import asyncio
import psycopg
from app.config import get_settings
from urllib.parse import urlparse, unquote

async def t():
    s = get_settings()
    # postgresql+asyncpg://postgres:Mahadev%401234@127.0.0.1:5432/meeting_scheduler
    url = urlparse(s.database_url.replace("+asyncpg", ""))
    
    params = {
        "user": url.username,
        "password": unquote(url.password) if url.password else None,
        "host": url.hostname,
        "port": url.port or 5432,
        "dbname": url.path.lstrip("/")
    }
    
    print(f"Connecting with params: user={params['user']}, host={params['host']}, dbname={params['dbname']}")
    try:
        async with await psycopg.AsyncConnection.connect(**params) as conn:
            print("✅ Connection successful with dict params!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(t())
