"""Run all services locally (for development)."""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROCS = []


def start(name: str, module: str, port: int):
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", f"{module}:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=str(ROOT),
        env={**__import__("os").environ, "PYTHONPATH": f"{ROOT}:{ROOT}/lt_common"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    PROCS.append((name, p))
    print(f"Started {name} on port {port} (pid={p.pid})")


def main():
    print("Starting ACE Platform services...")
    start("mock_sources", "mock_sources.main", 8200)
    time.sleep(1)
    start("data_injection_svc", "data_injection_svc.main", 8001)
    time.sleep(0.5)
    start("tracker_center_svc", "tracker_center_svc.main", 8002)
    time.sleep(0.5)
    start("ai_service", "ai_service.main", 8100)
    time.sleep(0.5)
    start("schedule_svc", "schedule_svc.main", 8000)
    print("\nAll services running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for name, p in PROCS:
            p.terminate()
            print(f"Stopped {name}")


if __name__ == "__main__":
    main()
