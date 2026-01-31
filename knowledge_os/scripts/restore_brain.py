import os
import sys
import subprocess
import shutil
from datetime import datetime

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def restore_system(backup_path):
    print(f"--- RECOVERY MODE START: {datetime.now()} ---")
    
    if not os.path.exists(backup_path):
        print(f"File {backup_path} not found!")
        return

    # 1. Prepare temp dir
    temp_dir = "/tmp/brain_restore"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # 2. Extract
    print("Extracting recovery bundle...")
    if not run_cmd(f"tar -xzf {backup_path} -C {temp_dir}"): return

    # 3. Restore Database
    print("Restoring Database...")
    sql_file = f"{temp_dir}/db_dump.sql"
    if os.path.exists(sql_file):
        drop_cmd = "docker exec -i knowledge_os_db psql -U admin -d knowledge_os -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'"
        restore_cmd = f"docker exec -i knowledge_os_db psql -U admin -d knowledge_os < {sql_file}"
        if run_cmd(drop_cmd) and run_cmd(restore_cmd):
            print("✅ Database restored.")
    
    # 4. Install Dependencies
    print("Checking dependencies...")
    req_file = f"{temp_dir}/requirements.txt"
    if os.path.exists(req_file):
        run_cmd(f"/usr/bin/python3 -m pip install -r {req_file}")
        print("✅ Dependencies updated.")

    # 5. Restart Services
    print("Restarting services...")
    run_cmd("pkill -f python3")
    # Launch logic (using original scripts)
    run_cmd("cd /root/knowledge_os/app && nohup python3 worker_v3.py >> worker.log 2>&1 &")
    run_cmd("cd /root/knowledge_os/dashboard && nohup python3 -m streamlit run app.py --server.port 5002 --server.address 0.0.0.0 >> brain.log 2>&1 &")
    
    print(f"--- RECOVERY COMPLETE: {datetime.now()} ---")
    print("System should be live at http://185.177.216.15:5002/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 restore_brain.py <path_to_backup.tar.gz>")
    else:
        restore_system(sys.argv[1])

