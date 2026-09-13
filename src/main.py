import asyncio

async def main():
    print("Привет")
    await asyncio.sleep(1)
    print("Пока")

asyncio.run(main())
