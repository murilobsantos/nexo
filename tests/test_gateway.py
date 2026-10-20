import json
import unittest
from unittest.mock import patch

import httpx

from nexo.gateway import Ollama


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def client(self, handler):
        original = httpx.AsyncClient
        transport = httpx.MockTransport(handler)
        return patch("nexo.gateway.httpx.AsyncClient", side_effect=lambda **kwargs: original(transport=transport, **kwargs))

    async def test_changed_digest_prevents_sending_private_prompt(self):
        gateway = Ollama()
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"models": [{"name": gateway.model, "digest": "changed"}]})
        with self.client(handler):
            self.assertTrue((await gateway.health())["model_changed"])
            with self.assertRaises(RuntimeError):
                async for _ in gateway.stream([{"role": "user", "content": "private fixture"}], 128):
                    pass
        self.assertTrue(all(request.method == "GET" and not request.content for request in requests))

    async def test_stream_uses_profile_and_preserves_terminal_evidence(self):
        gateway = Ollama()
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"models": [{"name": gateway.model, "digest": gateway.expected_digest}]})
            payload = json.loads(request.content)
            self.assertIs(payload["think"], False)
            self.assertEqual(payload["options"]["temperature"], 0.7)
            body = '\n'.join(json.dumps(row) for row in [{"message": {"content": "Resposta"}}, {"done": True, "done_reason": "stop", "eval_count": 5}])
            return httpx.Response(200, text=body)
        with self.client(handler):
            result = [row async for row in gateway.stream([{"role": "user", "content": "hello"}], 128)]
        self.assertEqual(result[0], {"text": "Resposta"})
        self.assertEqual(result[-1]["usage"]["eval_count"], 5)

    async def test_truncation_never_emits_success(self):
        gateway = Ollama()
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"models": [{"name": gateway.model, "digest": gateway.expected_digest}]})
            return httpx.Response(200, json={"message": {"content": "partial"}, "done": True, "done_reason": "length"})
        with self.client(handler), self.assertRaises(RuntimeError):
            async for _ in gateway.stream([], 128):
                pass
