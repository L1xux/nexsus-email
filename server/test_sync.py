import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_sync():
    from jose import jwt
    from datetime import datetime, timedelta

    # Generate a valid JWT for user 2
    secret = os.getenv("JWT_SECRET_KEY")
    data = {"sub": "2"}
    expire = datetime.utcnow() + timedelta(minutes=30)
    d = data.copy()
    d["exp"] = expire
    token = jwt.encode(d, secret, algorithm="HS256")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            "http://localhost:8000/api/emails/sync",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:500]}")

asyncio.run(test_sync())
