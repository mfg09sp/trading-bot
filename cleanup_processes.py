import subprocess
import os

my_pid = os.getpid()

ps_script = """
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' } | ForEach-Object {
    [PSCustomObject]@{
        Id = $_.ProcessId
        Cmd = $_.CommandLine
    }
} | ConvertTo-Json
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
import json
try:
    procs = json.loads(res.stdout)
    if isinstance(procs, dict):
        procs = [procs]
    for p in procs:
        pid = p.get("Id")
        cmd = p.get("Cmd") or ""
        if pid == my_pid:
            continue
        print(f"PID {pid} -> {cmd}")
        if any(target in cmd.lower() for target in ["polymarket_bot", "polymarket_monitor", "alpaca_monitor", "bot.py"]):
            print(f" --> Match! Killing {pid}")
            subprocess.run(["taskkill", "/F", "/PID", str(pid)])
except Exception as e:
    print(f"Error: {e}")
