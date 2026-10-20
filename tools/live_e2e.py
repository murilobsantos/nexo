"""Demonstração real: UI, modelo local, reinício e pausa. Requer runtime iniciado."""
import json
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
REPORT = ROOT / "reports" / "local-live-e2e.json"
report = {"checks": {}, "tasks": []}


def save():
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def check(name, result):
    report["checks"][name] = bool(result)
    save()
    assert result, name


def api(path, body=None):
    with httpx.Client(trust_env=False, timeout=15) as client:
        response = client.get(BASE + "/api" + path) if body is None else client.post(BASE + "/api" + path, json=body)
        response.raise_for_status()
        return response.json()


def wait_api():
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            return api("/state")
        except httpx.HTTPError:
            time.sleep(0.25)
    raise TimeoutError("Núcleo não iniciou")


def runtime_script(name, *args):
    # Pipes capturados podem permanecer abertos por descendentes no Windows.
    # Um arquivo de log não exige EOF de processos iniciados em segundo plano.
    log = ROOT / ".runtime" / "logs" / "e2e-runtime.log"
    with log.open("ab") as output:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools" / name), *args],
                                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=30)
    if result.returncode:
        raise RuntimeError("Falha no script " + name + "; consulte e2e-runtime.log")


def main():
    state = wait_api()
    check("backend_available", state["backend"]["available"] and state["backend"]["model_installed"])
    api("/mode", {"mode": "paused"})
    for task in api("/tasks"):
        if task["prompt"] == "Tarefa mantida na fila após reinício" and task["state"] == "ready":
            api(f"/tasks/{task['id']}/cancel", {})
    api("/mode", {"mode": "development"})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True, args=["--disable-gpu", "--disable-background-networking", "--no-first-run"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE, wait_until="networkidle")
            page.get_by_role("heading", name="Vamos conectar").wait_for()
            page.screenshot(path=str(ROOT / "reports" / "local-ui-desktop.png"), full_page=True)
            check("desktop_no_overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            prompt = "Leia este projeto de teste e explique como executá-lo. Cite README.md e pyproject.toml e apenas os comandos presentes nas fontes. Responda em até 120 palavras."
            page.get_by_label("Pedido para o NEXO").fill(prompt)
            with page.expect_response(lambda response: response.url.endswith("/api/tasks") and response.request.method == "POST") as created:
                page.get_by_role("button", name="Enviar tarefa").click()
            task = created.value.json()
            report["tasks"].append(task["id"])
            save()
            started = time.monotonic()
            next_update = started
            while time.monotonic() - started < 180:
                task = api("/tasks/" + task["id"])
                if task["state"] in {"completed", "failed", "waiting_resource", "cancelled"}:
                    break
                if time.monotonic() >= next_update:
                    print("Demo real:", task["state"], round(time.monotonic() - started, 1), "s", flush=True)
                    next_update = time.monotonic() + 20
                page.wait_for_timeout(500)
            report["demo_task"] = task
            save()
            check("real_model_demo_completed", task["state"] == "completed")
            check("demo_cites_sources", all(source in task["answer"] for source in ["README.md", "pyproject.toml", "python app.py"]))
            events = api(f"/tasks/{task['id']}/events")
            check("stream_and_source_evidence", any(event["kind"] == "delta" for event in events) and any(event["kind"] == "sources" for event in events))
            page.wait_for_timeout(1000)
            page.screenshot(path=str(ROOT / "reports" / "local-ui-conversation.png"), full_page=True)
            api("/mode", {"mode": "paused"})
            queued = api("/tasks", {"prompt": "Tarefa mantida na fila após reinício", "files": []})
            runtime_script("stop-nexo.ps1", "-KeepBackend")
            runtime_script("start-nexo.ps1")
            restarted = wait_api()
            check("restart_preserves_answer", api("/tasks/" + task["id"])["answer"] == task["answer"])
            check("restart_preserves_queue_and_pause", restarted["mode"] == "paused" and api("/tasks/" + queued["id"])["state"] == "ready")
            api(f"/tasks/{queued['id']}/cancel", {})
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(BASE, wait_until="networkidle")
            page.locator("select[aria-label='Histórico de tarefas']").select_option(task["id"])
            page.locator(".answer").wait_for()
            check("mobile_no_overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            page.screenshot(path=str(ROOT / "reports" / "local-ui-mobile.png"), full_page=True)
            check("browser_no_runtime_errors", not errors)
            api("/mode", {"mode": "development"})
            cancellation = api("/tasks", {"prompt": "Explique em detalhes e compare 50 estratégias para indexar projetos Python. Não seja breve.", "files": []})
            report["tasks"].append(cancellation["id"])
            deadline = time.monotonic() + 30
            model_started = False
            with httpx.Client(trust_env=False, timeout=5) as client:
                while time.monotonic() < deadline:
                    if client.get("http://127.0.0.1:11434/api/ps").json()["models"]:
                        model_started = True
                        break
                    time.sleep(0.2)
                check("cancel_test_real_model_loaded", model_started)
                started = time.monotonic()
                api("/mode", {"mode": "paused"})
                report["pause_seconds"] = time.monotonic() - started
                check("pause_under_two_seconds", report["pause_seconds"] < 2)
                check("running_task_paused", api("/tasks/" + cancellation["id"])["state"] == "paused")
                check("model_unloaded_after_pause", client.get("http://127.0.0.1:11434/api/ps").json()["models"] == [])
        finally:
            browser.close()
    report["result"] = "passed"
    save()
    print(REPORT, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        report["result"] = "failed"
        report["error"] = str(exc)
        save()
        raise
