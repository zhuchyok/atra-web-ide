import asyncio
import os
import sys

# Add knowledge_os/app to path
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))

async def test_success_retriever():
    try:
        from success_retriever import get_success_context

        query = "Как оптимизировать базу данных?"
        print(f"Testing Success Retriever with query: '{query}'")

        context = await get_success_context(query)

        if context:
            print("\nRetrieved Success Context:")
            print(context)
        else:
            print("\nNo relevant successful tasks found (yet).")

    except Exception as e:
        print(f"Error testing Success Retriever: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_success_retriever())
