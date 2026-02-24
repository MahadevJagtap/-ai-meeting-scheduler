import asyncio
import sys
import psycopg
from app.config import get_settings
from urllib.parse import urlparse, unquote

# Workaround for psycopg on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def t():
    s = get_settings()
    url = urlparse(s.database_url.replace("+asyncpg", ""))
    
    params = {
        "user": url.username,
        "password": unquote(url.password) if url.password else None,
        "host": url.hostname,
        "port": url.port or 5432,
        "dbname": url.path.lstrip("/")
    }
    
    print(f"Connecting ASYNC with SelectorEventLoop: user={params['user']}")
    try:
        async with await psycopg.AsyncConnection.connect(**params) as conn:
            print("✅ Async Connection successful with SelectorEventLoop!")
    except Exception as e:
        print(f"❌ Async Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(t())
