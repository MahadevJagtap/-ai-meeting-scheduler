import psycopg
from app.config import get_settings
from urllib.parse import urlparse, unquote

def t():
    s = get_settings()
    url = urlparse(s.database_url.replace("+asyncpg", ""))
    
    params = {
        "user": url.username,
        "password": unquote(url.password) if url.password else None,
        "host": url.hostname,
        "port": url.port or 5432,
        "dbname": url.path.lstrip("/")
    }
    
    print(f"Connecting SYNC with params: user={params['user']}, host={params['host']}, dbname={params['dbname']}")
    try:
        with psycopg.connect(**params) as conn:
            print("✅ Sync Connection successful!")
    except Exception as e:
        print(f"❌ Sync Connection failed: {e}")

if __name__ == "__main__":
    t()
