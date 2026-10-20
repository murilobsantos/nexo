"""Valida término e formato; não atribui qualidade semântica ao modelo."""
import argparse
import json
from pathlib import Path


def review(report):
    rows = []
    for item in report["samples"]:
        result = item.get("result", {})
        text = result.get("response", "").strip()
        complete = bool(text) and result.get("done") is True and result.get("done_reason") == "stop"
        row = {"id": item["id"], "context": item["context"], "complete_final_answer": complete,
               "semantic_review": "pending", "elapsed_seconds": item.get("elapsed_seconds"),
               "tokens_per_second": item.get("tokens_per_second")}
        if item["id"] == "tool":
            try:
                payload = json.loads(text)
                row["exact_tool_selection"] = payload == {"tool": "read_file", "arguments": {"path": "demo/README.md"}}
            except (ValueError, TypeError):
                row["exact_tool_selection"] = False
        rows.append(row)
    return {"samples": rows, "product_acceptance": "not_run",
            "warning": "Resposta completa e JSON correto não comprovam correção geral nem permissões."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(review(json.loads(args.report.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
