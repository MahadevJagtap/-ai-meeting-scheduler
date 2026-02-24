import httpx
import sys

try:
    response = httpx.get("http://localhost:8000/health", timeout=5.0)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
    if response.status_code == 200:
        print("✅ Health check PASSED")
    else:
        print("❌ Health check FAILED")
except Exception as e:
    print(f"❌ Error during health check: {e}")
    sys.exit(1)
