"""Amostragem limitada aos processos Ollama; requer psutil do ambiente de prova."""
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]


def sample(scope="backend"):
    processes = []
    runtime = (ROOT / ".runtime" / "ollama").resolve()
    core_ids = set()
    if scope in {"core", "all"}:
        try:
            core = psutil.Process(int((ROOT / ".runtime" / "nexo.pid").read_text().strip()))
            if Path(core.exe()).resolve() == (ROOT / ".venv" / "Scripts" / "python.exe").resolve():
                core_ids = {core.pid, *(child.pid for child in core.children(recursive=True))}
        except (OSError, ValueError, psutil.Error):
            pass
    for proc in psutil.process_iter(["pid", "name", "exe", "memory_info", "cpu_times"]):
        try:
            executable = proc.info["exe"]
            backend_match = scope in {"backend", "all"} and executable and Path(executable).resolve().is_relative_to(runtime)
            if backend_match or proc.pid in core_ids:
                processes.append({"pid": proc.pid, "rss": proc.info["memory_info"].rss,
                                  "cpu_seconds": sum(proc.info["cpu_times"][:2])})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"elapsed_clock": time.monotonic(), "processes": processes,
            "available_ram_bytes": psutil.virtual_memory().available,
            "gpu_raw": gpu.stdout.strip(), "gpu_exit_code": gpu.returncode}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--label", choices=["idle", "generation"], required=True)
    parser.add_argument("--scope", choices=["backend", "core", "all"], default="backend")
    args = parser.parse_args()
    label = args.label if args.scope == "backend" else args.scope + "-" + args.label
    target = ROOT / "reports" / f"local-resources-{label}-{time.time_ns()}.json"
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "label": args.label,
              "logical_cpus": psutil.cpu_count(), "sleep_between_samples_seconds": 2,
              "scope": args.scope, "samples": []}
    while True:
        report["samples"].append(sample(args.scope))
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if report["samples"][-1]["elapsed_clock"] - report["samples"][0]["elapsed_clock"] >= args.seconds:
            break
        time.sleep(2)
    print(target)
