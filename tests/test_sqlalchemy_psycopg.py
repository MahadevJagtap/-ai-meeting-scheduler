import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings

async def test_psycopg():
    settings = get_settings()
    # Replace asyncpg with psycopg
    url = settings.database_url.replace("asyncpg", "psycopg")
    print(f"Testing URL: {url}")
    
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"Select 1: {result.scalar()}")
            print("✅ SQLAlchemy + psycopg working!")
    except Exception as e:
        print(f"❌ SQLAlchemy + psycopg failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_psycopg())
