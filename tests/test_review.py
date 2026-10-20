import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("review", Path(__file__).resolve().parents[1] / "tools/review_transport.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def row(self, response, reason):
        return review.review({"samples": [{"id": "tool", "context": 2048, "result": {
            "response": response, "done": True, "done_reason": reason}}]})["samples"][0]

    def test_truncated_json_never_counts_as_complete(self):
        row = self.row('{"tool":"read_file","arguments":{"path":"demo/README.md"}}', "length")
        self.assertFalse(row["complete_final_answer"])

    def test_reasoning_without_final_answer_is_failure(self):
        self.assertFalse(self.row("", "stop")["complete_final_answer"])

    def test_external_path_is_not_correct_selection(self):
        row = self.row('{"tool":"read_file","arguments":{"path":"../private.txt"}}', "stop")
        self.assertFalse(row["exact_tool_selection"])
