import asyncio
import os
import asyncpg

import getpass
USER = getpass.getuser()
DB_URL = os.getenv('DATABASE_URL', f'postgresql://{USER}@localhost:5432/knowledge_os')

async def init_system():
    try:
        conn = await asyncpg.connect(DB_URL)
        
        # 1. Create System domain
        print("🔧 Ensuring System domain exists...")
        await conn.execute("""
            INSERT INTO domains (name, description)
            VALUES ('System', 'System migrations and core knowledge')
            ON CONFLICT (name) DO NOTHING
        """)
        
        # 2. Create Management domain (for Victoria)
        print("🔧 Ensuring Management domain exists...")
        await conn.execute("""
            INSERT INTO domains (name, description)
            VALUES ('Management', 'Team management and coordination')
            ON CONFLICT (name) DO NOTHING
        """)
        
        await conn.close()
        print("✅ Base domains created.")
        
        # 3. Run orchestrator to apply migrations
        print("🚀 Running orchestrator to apply migrations...")
        
        # Get the absolute path to the app directory relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.abspath(os.path.join(script_dir, "../app"))
        
        import sys
        sys.path.append(app_dir)
        
        os.chdir(app_dir)
        from enhanced_orchestrator import run_enhanced_orchestration_cycle
        await run_enhanced_orchestration_cycle()
        
        print("✨ Singularity v3.0 Infrastructure is fully initialized and active!")
        
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(init_system())

