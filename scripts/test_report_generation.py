import asyncio
import os
import sys

# Add knowledge_os/app to sys.path
sys.path.append(os.path.join(os.getcwd(), "knowledge_os/app"))

from report_generator import get_report_generator

async def test_report():
    gen = get_report_generator()
    report = await gen.generate_daily_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(test_report())
