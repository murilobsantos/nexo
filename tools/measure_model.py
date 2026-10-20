"""Mede recursos do perfil selecionado durante uma geração sintética local."""
import asyncio
import json
import time
from pathlib import Path

import psutil

from nexo.gateway import Ollama
from resources import sample
from summarize_resources import summarize

ROOT = Path(__file__).resolve().parents[1]


async def main():
    gateway = Ollama()
    report = {"model": gateway.model, "digest": gateway.expected_digest, "scope": "backend",
              "logical_cpus": psutil.cpu_count(), "samples": []}
    path = ROOT / "reports" / f"local-profile-resources-{time.time_ns()}.json"
    stop = False
    async def collect():
        while not stop:
            report["samples"].append(await asyncio.to_thread(sample, "backend"))
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            await asyncio.sleep(0.5)
    collector = asyncio.create_task(collect())
    try:
        await asyncio.sleep(0.8)
        started = time.monotonic()
        count = 0
        async for chunk in gateway.stream([{"role": "user", "content": "Explique em português, em até 500 palavras, as etapas de preparar uma alteração de código, testar em cópia isolada, revisar o diff, aplicar e restaurar. Não execute ações."}], 2560):
            count += len(chunk.get("text", ""))
            if chunk.get("done"):
                report["usage"] = chunk.get("usage")
                report["generation_completed"] = True
        report["request_elapsed_seconds"] = time.monotonic() - started
        report["output_characters"] = count
    finally:
        try:
            await gateway.unload()
        finally:
            await asyncio.sleep(1)
            stop = True
            await collector
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    result = {"model": gateway.model, "digest": gateway.expected_digest, **summarize(report),
              "request_elapsed_seconds": report["request_elapsed_seconds"],
              "generation_completed": report.get("generation_completed", False),
              "note": "Janela inclui carregamento, geração e descarga; média CPU não é exclusiva de geração. Não é medição ociosa de cinco minutos."}
    (ROOT / "reports/model-resource-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
