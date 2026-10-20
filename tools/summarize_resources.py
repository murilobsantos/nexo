"""Resume observações; RSS de múltiplos processos pode contar páginas compartilhadas."""
import argparse
import json
from pathlib import Path


def summarize(report):
    samples = report["samples"]
    duration = samples[-1]["elapsed_clock"] - samples[0]["elapsed_clock"]
    cpu_by_pid = {}
    for row in samples:
        for proc in row["processes"]:
            cpu_by_pid.setdefault(proc["pid"], []).append(proc["cpu_seconds"])
    cpu = sum(max(times) - min(times) for times in cpu_by_pid.values())
    gpu_values = [int(row["gpu_raw"].split(",")[0]) for row in samples
                  if row["gpu_exit_code"] == 0 and row["gpu_raw"]]
    peak_rss = max(sum(p["rss"] for p in s["processes"]) for s in samples)
    cpu_percent = cpu / duration / report["logical_cpus"] * 100 if duration else None
    result = {"duration_seconds": duration, "sample_count": len(samples),
            "scope": report.get("scope", "backend"), "peak_process_rss_mib": peak_rss / 1024**2,
            "processes_observed_in_all_samples": all(bool(sample["processes"]) for sample in samples),
            "peak_system_gpu_used_mib": max(gpu_values) if gpu_values else None,
            "average_machine_cpu_percent_approx": cpu_percent,
            "minimum_available_ram_mib": min(s["available_ram_bytes"] for s in samples) / 1024**2,
            "limitations": "GPU é uso total do sistema. Amostras podem perder picos; CPU subestima processos transitórios; RSS agregado pode contar páginas compartilhadas. Não mede interferência em jogos.",
            "five_minute_window": duration >= 300}
    if report.get("scope", "backend") != "core":
        result["peak_ollama_rss_mib"] = peak_rss / 1024**2
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.report.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
