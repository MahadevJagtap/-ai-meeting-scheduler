import httpx
import asyncio

async def trigger_schedule():
    url = "http://localhost:8000/api/schedule"
    payload = {
        "user_id": "test_user_whatsapp",
        "request_text": "Schedule a 15 min catch-up with my brother today at 16:00",
        "participants": ["sharadpatil1704@gmail.com"],
        "timezone_offset": 330 # IST
    }
    
    print(f"Sending request to {url}...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_schedule())
