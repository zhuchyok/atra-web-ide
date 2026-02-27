import httpx
import asyncio
import json

async def test():
    async with httpx.AsyncClient() as client:
        print("Sending request...")
        async with client.stream(
            "POST",
            "http://localhost:8010/stream",
            json={"goal": "привет", "project_context": "test"}
        ) as r:
            print(f"Status: {r.status_code}")
            async for line in r.aiter_lines():
                print(f"LINE: {line}")

if __name__ == "__main__":
    asyncio.run(test())
