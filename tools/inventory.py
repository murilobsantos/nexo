"""Inventário limitado a versões e recursos; não coleta arquivos pessoais."""
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"exit_code": p.returncode, "output": (p.stdout + p.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def snapshot():
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "disk": {drive: dict(zip(("total", "used", "free"), shutil.disk_usage(drive)))
                 for drive in ("C:/", "D:/") if Path(drive).exists()},
        "node": command(["node", "--version"]),
        "npm": command(["npm.cmd", "--version"]),
        "git": command(["git", "--version"]),
        "gpu": command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader"]),
        "memory": command(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress"]),
    }


if __name__ == "__main__":
    target = ROOT / "reports" / "local-inventory.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)
