import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("benchmark", Path(__file__).resolve().parents[1] / "tools/benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class RequestTests(unittest.TestCase):
    def test_rejects_oversized_backend_response(self):
        response = io.BytesIO(b" " * (benchmark.MAX_RESPONSE + 1))
        with patch.object(benchmark.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with self.assertRaises(ValueError):
                benchmark.request("/api/tags")

    def test_only_loopback_and_no_proxy(self):
        with patch.object(benchmark.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"models":[]}')
            self.assertEqual(benchmark.request("/api/tags"), {"models": []})
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "http://127.0.0.1:11434/api/tags")

    def test_acceptance_distribution_and_unique_ids(self):
        from collections import Counter
        cases = json.loads((Path(__file__).resolve().parents[1] / "evals/acceptance.json").read_text(encoding="utf-8"))
        self.assertEqual(len({c["id"] for c in cases}), 20)
        self.assertEqual(Counter(c["category"] for c in cases),
                         {"bug": 5, "feature": 4, "research": 4, "organization": 3, "memory": 2, "coexistence": 2})


if __name__ == "__main__":
    unittest.main()
