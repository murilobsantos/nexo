"""Aceite real de desenvolvimento em dois projetos sintéticos independentes."""
import asyncio
import json
import subprocess
import time
import uuid
import argparse
import os
from pathlib import Path

from fastapi.testclient import TestClient

from nexo.api import create_app
from nexo.runner import Runner
from nexo.gateway import Ollama

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "local-development-e2e.json"
report = {"cases": [], "checks": {}}
gateway_options = {}


def save():
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(root / ".no-hooks"), "-C", str(root), *args],
                            capture_output=True, timeout=10, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))


def fixture(name):
    root = ROOT / ".runtime" / "development-eval" / (name + "-" + uuid.uuid4().hex)
    project = root / "project"
    (project / "tests").mkdir(parents=True)
    (project / "app.py").write_text("def media(values):\n    return None if not values else sum(values) / len(values)\n", encoding="utf-8")
    (project / "README.md").write_text("Projeto de avaliação. Testes: python -m unittest discover -s tests -v\n", encoding="utf-8")
    tests = "import unittest\nimport app\nclass T(unittest.TestCase):\n    def test_empty(self): self.assertIsNone(app.media([]))\n    def test_pair(self): self.assertEqual(app.media([2,4]),3)\n"
    (project / "tests/test_app.py").write_text(tests, encoding="utf-8")
    git(project, "init", "-q")
    git(project, "add", ".")
    git(project, "-c", "user.name=NEXO fixture", "-c", "user.email=nexo@example.invalid", "commit", "-qm", "baseline fixture")
    if name == "bug":
        (project / "app.py").write_text("# Comentário pré-existente do usuário; preservar.\ndef media(values):\n    return sum(values) / len(values)\n", encoding="utf-8")
    else:
        (project / "app.py").write_text("# Comentário pré-existente do usuário; preservar.\ndef media(values):\n    return None if not values else sum(values) / len(values)\n", encoding="utf-8")
        tests += "    def test_median_empty(self): self.assertIsNone(app.mediana([]))\n    def test_median_odd(self): self.assertEqual(app.mediana([3,1,2]),2)\n    def test_median_even(self): self.assertEqual(app.mediana([4,1,3,2]),2.5)\n    def test_no_mutation(self):\n        values=[3,1,2]\n        app.mediana(values)\n        self.assertEqual(values,[3,1,2])\n"
        (project / "tests/test_app.py").write_text(tests, encoding="utf-8")
    (project / "notes.txt").write_bytes("Anotação não rastreada — não apagar.\r\n".encode("utf-8"))
    return root, project


def run_case(name, objective):
    root, project = fixture(name)
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file() and ".git" not in p.relative_to(project).parts}
    case = {"name": name, "project": str(project), "objective": objective}
    report["cases"].append(case)
    save()
    app = create_app(data_dir=root / "data", project_dir=project, gateway=Ollama(**gateway_options))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.post("/api/mode", json={"mode": "development"}).raise_for_status()
        response = client.post("/api/tasks", json={"kind": "development", "prompt": objective,
            "files": ["app.py"], "timeout_seconds": 300})
        response.raise_for_status()
        task = response.json()
        case["task_id"] = task["id"]
        save()
        start = time.monotonic()
        update = start
        while time.monotonic() - start < 310:
            task = client.get("/api/tasks/" + task["id"]).json()
            if task["state"] in {"waiting_user", "completed", "failed", "waiting_resource", "cancelled"}:
                break
            if time.monotonic() >= update:
                events = client.get(f"/api/tasks/{task['id']}/events").json()
                print(name, task["state"], round(time.monotonic() - start, 1), "s", events[-1]["kind"] if events else "", flush=True)
                update = time.monotonic() + 20
            time.sleep(0.25)
        case["task"] = task
        case["elapsed_seconds"] = time.monotonic() - start
        save()
        assert task["state"] == "waiting_user", task
        candidate = client.get(f"/api/tasks/{task['id']}/development").json()
        case["candidate"] = candidate
        save()
        assert candidate["status"] == "review" and candidate["files"]
        assert all(p.read_bytes() == before[p.relative_to(project).as_posix()] for p in project.rglob("*") if p.is_file() and ".git" not in p.relative_to(project).parts)
        # Aplicação local já autorizada pelo objetivo; não publica nada externamente.
        applied = client.post(f"/api/tasks/{task['id']}/development/publish", json={})
        applied.raise_for_status()
        assert client.get("/api/tasks/" + task["id"]).json()["state"] == "completed"
        assert "Comentário pré-existente do usuário; preservar." in (project / "app.py").read_text(encoding="utf-8")
        assert (project / "notes.txt").read_bytes() == before["notes.txt"]
        verification = asyncio.run(Runner().run(project, "python-tests"))
        case["source_verification"] = verification
        assert verification["passed"], verification
        restored = client.post(f"/api/tasks/{task['id']}/development/restore", json={})
        restored.raise_for_status()
        assert all((project / path).read_bytes() == data for path, data in before.items())
        case["checks"] = {"real_model_proposal_ready": True, "tests_passed_in_copy": True,
            "source_untouched_before_apply": True, "applied_tests_passed": True,
            "preexisting_comment_preserved": True, "untracked_bytes_preserved": True,
            "restored_original_bytes": True}
        save()
        print(name, "passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--no-thinking", action="store_true")
    args = parser.parse_args()
    gateway_options.update(model=args.model, thinking=not args.no_thinking)
    report["gateway"] = gateway_options
    try:
        run_case("bug", "Corrija apenas media em app.py: lista vazia deve retornar None; [2,4] retorna 3. Preserve o comentário pré-existente e todo código fora da função. Faça um patch mínimo.")
        run_case("feature", "Adicione mediana(values) em app.py. Retorne None para lista vazia; mediana de [3,1,2] é 2 e de [4,1,3,2] é 2.5. Não altere a lista recebida. Preserve media e o comentário pré-existente. Faça um patch mínimo.")
        report["result"] = "passed"
        save()
    except BaseException as exc:
        report["result"] = "failed"
        report["error"] = str(exc)
        save()
        raise
