import asyncio
import sys
import os

# Add paths
sys.path.append("/app/knowledge_os")
sys.path.append("/app/knowledge_os/app")

async def test():
    from app.ai_core import run_smart_agent_async
    print("Starting request for Oleg...")
    try:
        r = await run_smart_agent_async(
            "Привет, Олег! Расскажи о себе кратко.",
            expert_name="Олег",
            category="reasoning"
        )
        print(f"Result: {r}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
