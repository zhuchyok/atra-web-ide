import asyncio
import sys
import os

# Add knowledge_os/app to path to import browser_operator
sys.path.append(os.path.join(os.getcwd(), "knowledge_os/app"))

try:
    from browser_operator import get_browser_operator
except ImportError:
    print("Error: Could not import browser_operator. Make sure you are in the project root.")
    sys.exit(1)

async def check_price():
    operator = get_browser_operator()
    goal = """Navigate to https://setkimoskitki.ru
    Wait for the page to load.
    Find the 'Предварительная цена' (Preliminary price) in the calculator.
    The default settings should be 350x1000, standard mesh.
    Report the exact price number shown.
    Also, take a screenshot if possible or just describe what you see."""
    
    try:
        result = await operator.execute_task(goal)
        print(f"RESULT: {result}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(check_price())
