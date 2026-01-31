
import subprocess, os, time

PYTHON_EXEC = "/root/knowledge_os/venv/bin/python3"

def start(cmd, log):
    print(f"Starting: {cmd}")
    with open(log, "a") as f:
        env = os.environ.copy()
        env["PYTHONPATH"] = "/root/knowledge_os/app"
        env["DATABASE_URL"] = "postgresql://admin:secret@localhost:5432/knowledge_os"
        subprocess.Popen(cmd, shell=True, stdout=f, stderr=f, start_new_session=True, env=env)

# Kill old ones
subprocess.run("fuser -k 8000/tcp; pkill -f streamlit; pkill -f main_enhanced.py; pkill -f vector_core.py; pkill -f telegram_simple.py; pkill -f nightly_learner.py; pkill -f enhanced_orchestrator.py; pkill -f smart_worker", shell=True)
time.sleep(2)

# 1. Dashboard
start(f"cd /root/knowledge_os/dashboard && {PYTHON_EXEC} -m streamlit run app.py --server.port 5002 --server.address 0.0.0.0", "/root/dashboard_new.log")

# 2. MCP Server
start(f"cd /root/knowledge_os/app && {PYTHON_EXEC} main_enhanced.py", "/root/mcp_server_new.log")

# 3. Vector Core
start(f"cd /root/knowledge_os/app && {PYTHON_EXEC} vector_core.py", "/root/vector_core_new.log")

# 4. Telegram Gateway
start(f"{PYTHON_EXEC} /root/knowledge_os/app/telegram_simple.py", "/root/tg_new.log")

# 5. Nightly Learner (Accelerated)
start(f"{PYTHON_EXEC} /root/knowledge_os/app/nightly_learner.py", "/root/learner_new.log")

# 6. Enhanced Orchestrator (Autonomous Loop)
start(f"while true; do {PYTHON_EXEC} /root/knowledge_os/app/enhanced_orchestrator.py; sleep 300; done", "/root/orchestrator_new.log")

# 7. Autonomous Smart Worker
start(f"{PYTHON_EXEC} /root/knowledge_os/app/smart_worker_autonomous.py", "/root/smart_worker.log")

print("All Knowledge OS modules (Autonomous) triggered.")
