import os
import subprocess


def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
    except Exception as e:
        return str(e)


print("=== SYSTEM AUDIT: TIMEOUT STORM DIAGNOSIS ===")
print("[System] Mac Studio M4 Max | Unified Memory Architecture\n")

# 1. Проверка процессов MLX и Ollama (PID, CPU%, MEM%)
os.system('echo "--- ACTIVE INFERENCE PROCESSES ---"')
p = run_cmd("ps aux | grep -E '(mlx|ollama)' | grep -v 'grep'")
print(p if p else "[OK] No active MLX/Ollama processes found.")

# 2. Глобальный обзор памяти (Physical RAM)
os.system('echo "\n--- SYSTEM MEMORY STATUS ---"')
p = run_cmd("sysctl hw.memsize")
print(f"Total Physical Memory: {int(p.split()[-1]) / 10**9:.1f} GB")

# 3. Проверка Swap Usage (Критично для предотвращения OOM)
os.system('echo "\n--- SWAP USAGE (CRITICAL FOR M4 MAX) ---"')
p = run_cmd("sysctl vm.swapusage | awk -F'[()]' '{print $2}'")
# Форматируем вывод sysctl
swap_total, swap_used, swap_max = p.split()
print(f"Swap Total: {int(swap_total) / 10**6:.1f} GB")
print(f"Swap Used : {int(swap_used) / 10**6:.2f} GB (HIGH LATENCY RISK)")

# 4. Виртуальная память и пулы памяти
os.system('echo "\n--- MEMORY PAGES STATUS ---"')
p = run_cmd("vm_stat | grep -E 'Pages free|Wire' | awk '{print $2/1024, $3}'")
lines = p.split("\n")
if len(lines) >= 2:
    print(f"Free Pages (MB): {float(lines[0].split()[0]):.1f}")
    print(
        f"Wired/Memory Locked: {float(lines[-1].split()[0]):.1f} MB"
    )  # wired - память, которую нельзя выгрузить

print("\n--- AUDIT COMPLETE ---")
