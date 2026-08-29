#!/usr/bin/env python3
"""Run the experiment suite as a background process.

Usage examples:
  python run_exp_python.py
  python run_exp_python.py --all-scenarios --replications 5
  python run_exp_python.py --scenario low_demand --strategy auction --replications 2
"""
import os
import subprocess
import sys
import time

SIM_DIR = os.path.dirname(os.path.abspath(__file__))

env = os.environ.copy()
if "SUMO_HOME" not in env:
    sumo_candidates = [
        "/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo",
        "/usr/share/sumo",
        "/usr/local/share/sumo",
    ]
    sumo_home = next((p for p in sumo_candidates if os.path.isdir(p)), None)
    if sumo_home:
        env["SUMO_HOME"] = sumo_home
if "SUMO_HOME" in env:
    env["PATH"] = env["SUMO_HOME"] + os.sep + "bin" + os.pathsep + env.get("PATH", "")
env["PYTHONUNBUFFERED"] = "1"

try:
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/F", "/IM", "sumo.exe"], timeout=5, capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "sumo-gui.exe"], timeout=5, capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "sumo.*remote-port"], timeout=5)
except Exception:
    pass

time.sleep(2)

experiments_script = os.path.join(SIM_DIR, "experiments.py")
python = sys.executable
output_dir = os.path.join(SIM_DIR, "output")

cmd = [python, experiments_script] + sys.argv[1:]
cmd += ["--output-dir", output_dir]

log_path = os.path.join(output_dir, "experiment_run.log")
os.makedirs(output_dir, exist_ok=True)

print(f"Starting experiment at {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Working dir: {SIM_DIR}")
print(f"Log: {log_path}")
print(f"Command: {' '.join(cmd)}")

with open(log_path, "w") as log_file:
    proc = subprocess.Popen(
        cmd,
        cwd=SIM_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    for line in proc.stdout:
        print(line, end="", flush=True)
        log_file.write(line)

    proc.wait()

print(f"\nFinished with exit code {proc.returncode} at {time.strftime('%Y-%m-%d %H:%M:%S')}")

results_path = os.path.join(output_dir, "csv", "experiment_results.csv")
if os.path.exists(results_path):
    with open(results_path) as f:
        lines = f.readlines()
    print(f"Results: {len(lines)} lines (including header)")
    true_count = sum(1 for l in lines[1:] if ",True" in l)
    print(f"sumo_connected=True: {true_count}/{len(lines)-1}")
else:
    print("ERROR: experiment_results.csv not found!")
