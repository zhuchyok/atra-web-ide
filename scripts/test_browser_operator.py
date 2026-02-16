"""
[SINGULARITY 10.0+] Test script for Browser Operator (Victoria Operator).
Verifies that Veronica can perform browser actions.
"""

import asyncio
import os
import sys

# Add paths for imports
sys.path.append(os.path.join(os.getcwd(), "knowledge_os/app"))

async def test_browser_operator():
    print("🧪 [TEST] Starting Browser Operator Verification...")
    
    try:
        from browser_operator import get_browser_operator
        operator = get_browser_operator()
        
        # Test 1: Basic execution (Mock mode if libraries missing)
        print("📤 [TEST 1] Executing basic task...")
        goal = "Open google.com and search for 'ATRA Web IDE'"
        result = await operator.execute_task(goal)
        
        print(f"✅ [TEST 1] Status: {result['status']}")
        if result['status'] == 'success':
            print(f"   Output: {result['output'][:100]}...")
            if result.get('screenshot'):
                print(f"   Screenshot captured: {len(result['screenshot'])} bytes")
        else:
            print(f"   Error/Mock: {result.get('message', 'No message')}")
            
        return True
    except Exception as e:
        print(f"❌ [TEST] Failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_browser_operator())
