"""Verifica na UI real criar proposta, aplicar e restaurar no projeto de avaliação."""
import asyncio
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psutil
from playwright.sync_api import sync_playwright

from nexo.runner import Runner

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8766"
REPORT = ROOT / "reports" / "local-development-ui.json"
result = {"checks": {}}


def record(name, condition):
    result["checks"][name] = bool(condition)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert condition, name


def api(path, body=None):
    with httpx.Client(trust_env=False, timeout=10) as client:
        response = client.get(BASE + "/api" + path) if body is None else client.post(BASE + "/api" + path, json=body)
        response.raise_for_status()
        return response.json()


def main():
    previous = json.loads((ROOT / "reports/local-development-e2e.json").read_text(encoding="utf-8"))
    assert previous["result"] == "passed"
    fixture = previous["cases"][-1]
    project = Path(fixture["project"])
    before = (project / "app.py").read_bytes()
    notes = (project / "notes.txt").read_bytes()
    log = (ROOT / ".runtime/logs/development-ui-server.log").open("ab")
    process = subprocess.Popen([str(ROOT / ".venv/Scripts/python.exe"), "-m", "nexo", "--port", "8766", "--project", str(project),
        "--data-dir", str(project.parent / "data")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    identity = psutil.Process(process.pid)
    try:
        for _ in range(100):
            try:
                api("/state")
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        api("/mode", {"mode": "development"})
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True, args=["--disable-gpu", "--disable-background-networking", "--no-first-run"])
            try:
                page = browser.new_page(viewport={"width":1440,"height":1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(BASE, wait_until="networkidle")
                page.locator(".file-list label").filter(has_text="app.py").first.wait_for()
                page.get_by_label("Tipo de tarefa").select_option("development")
                page.get_by_label("Pedido para o NEXO").fill(fixture["objective"])
                with page.expect_response(lambda response: response.url.endswith("/api/tasks") and response.request.method == "POST") as created:
                    page.get_by_role("button", name="Enviar tarefa").click()
                task = created.value.json()
                result["task_id"] = task["id"]
                start = time.monotonic()
                for _ in range(360):
                    task = api("/tasks/" + task["id"])
                    if task["state"] in {"waiting_user", "completed", "failed"}:
                        break
                    page.wait_for_timeout(500)
                record("model_proposal_ready_from_ui", task["state"] == "waiting_user")
                record("source_untouched_before_apply", (project / "app.py").read_bytes() == before)
                page.get_by_role("button", name="Aplicar ao projeto").wait_for(timeout=15000)
                record("diff_visible", bool(page.get_by_label("Diff da alteração").inner_text()))
                record("desktop_no_overflow", page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
                page.screenshot(path=str(ROOT / "reports/local-development-ui-desktop.png"), full_page=True)
                page.get_by_role("button", name="Aplicar ao projeto").click()
                page.get_by_role("button", name="Restaurar original").wait_for()
                # A API sync do Playwright mantém um loop no mesmo thread.
                with ThreadPoolExecutor(max_workers=1) as executor:
                    verification = executor.submit(lambda: asyncio.run(Runner().run(project, "python-tests"))).result(timeout=40)
                record("applied_source_tests_pass", verification["passed"])
                page.get_by_role("button", name="Restaurar original").click()
                page.get_by_text("Original restaurado", exact=True).wait_for()
                record("restore_exact_bytes", (project / "app.py").read_bytes() == before)
                record("untracked_preserved", (project / "notes.txt").read_bytes() == notes)
                page.get_by_role("button", name="Nova tarefa", exact=False).click()
                page.get_by_label("Pedido para o NEXO").fill(fixture["objective"])
                with page.expect_response(lambda response: response.url.endswith("/api/tasks") and response.request.method == "POST") as second:
                    page.get_by_role("button", name="Enviar tarefa").click()
                rejected_task = second.value.json()
                result["rejected_task_id"] = rejected_task["id"]
                page.get_by_role("button", name="Rejeitar proposta").wait_for(timeout=180000)
                page.get_by_role("button", name="Rejeitar proposta").click()
                page.get_by_text("Proposta rejeitada", exact=True).wait_for()
                record("rejected_source_untouched", (project / "app.py").read_bytes() == before)
                page.set_viewport_size({"width":390,"height":844})
                record("mobile_no_overflow", page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
                page.screenshot(path=str(ROOT / "reports/local-development-ui-mobile.png"), full_page=True)
                record("no_javascript_errors", not errors)
                result["elapsed_seconds"] = time.monotonic() - start
            finally:
                browser.close()
        result["result"] = "passed"
    except BaseException as exc:
        result["result"] = "failed"
        result["error"] = str(exc)
        raise
    finally:
        if result.get("task_id"):
            try:
                candidate = api(f"/tasks/{result['task_id']}/development")
                if candidate["status"] == "applied":
                    api(f"/tasks/{result['task_id']}/development/restore", {})
                    result["cleanup_restored"] = True
            except httpx.HTTPError as exc:
                result["cleanup_error"] = str(exc)
        try:
            api("/mode", {"mode":"paused"})
        except httpx.HTTPError:
            pass
        if identity.is_running():
            subprocess.run(["taskkill", "/PID", str(identity.pid), "/T", "/F"], capture_output=True, timeout=10)
        process.wait(timeout=5)
        log.close()
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(REPORT, flush=True)


if __name__ == "__main__":
    main()
