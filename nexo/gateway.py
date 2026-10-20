"""Adaptador Ollama local com streaming e cancelamento de conexão."""
import asyncio
import json
from pathlib import Path

import httpx


class Ollama:
    def __init__(self, model=None, base="http://127.0.0.1:11434", context=None, thinking=None):
        if base != "http://127.0.0.1:11434":
            raise ValueError("Somente backend loopback aprovado nesta versão")
        profile = json.loads((Path(__file__).resolve().parents[1] / "model-profile.json").read_text(encoding="utf-8"))
        selected_default = model is None
        self.model, self.base, self.context = model or profile["model"], base, context or profile["context"]
        self.thinking = profile["thinking"] if selected_default and thinking is None else thinking
        self.expected_digest = profile["digest"] if self.model == profile["model"] else None
        if self.context not in {2048, 4096}:
            raise ValueError("Contexto fora das configurações medidas")
        use_profile = self.model == profile["model"] and self.thinking == profile["thinking"]
        self.temperature = profile["temperature"] if use_profile else (0.7 if self.thinking is False else 0.6)
        self.top_p = profile["top_p"] if use_profile else (0.8 if self.thinking is False else 0.95)

    async def stream(self, messages, max_tokens):
        async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(15, read=180)) as client:
            if self.expected_digest:
                catalog = await client.get(self.base + "/api/tags")
                catalog.raise_for_status()
                matching = [model for model in catalog.json()["models"] if model["name"] == self.model]
                if not matching:
                    raise ConnectionError("Modelo selecionado não está instalado")
                if matching[0]["digest"] != self.expected_digest:
                    raise RuntimeError("Modelo instalado mudou; reavalie antes de usar o perfil")
            async with client.stream("POST", self.base + "/api/chat", json={
                "model": self.model, "messages": messages, "stream": True, "think": self.thinking,
                "keep_alive": 0, "options": {"num_ctx": self.context, "num_predict": max_tokens,
                    "temperature": self.temperature, "top_p": self.top_p, "top_k": 20, "seed": 42},
            }) as response:
                response.raise_for_status()
                total = 0
                async for line in response.aiter_lines():
                    if len(line) > 65536:
                        raise ValueError("Frame do backend excede limite")
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise RuntimeError("Backend recusou a geração")
                    text = data.get("message", {}).get("content", "")
                    total += len(text.encode("utf-8"))
                    if total > 65536:
                        raise ValueError("Resposta excede 64 KiB")
                    if text:
                        yield {"text": text}
                    if data.get("done"):
                        if data.get("done_reason") != "stop":
                            raise RuntimeError("Resposta incompleta: limite de saída atingido")
                        yield {"done": True, "usage": {key: data.get(key) for key in (
                            "eval_count", "eval_duration", "prompt_eval_count", "total_duration")}}
                        return
                raise RuntimeError("Conexão terminou antes da conclusão")

    async def unload(self):
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            response = await client.post(self.base + "/api/generate", json={"model": self.model, "keep_alive": 0})
            response.raise_for_status()

    async def health(self):
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
                response = await client.get(self.base + "/api/tags")
                response.raise_for_status()
                matching = [model for model in response.json()["models"] if model["name"] == self.model]
                return {"available": True, "model_installed": bool(matching),
                        "model_changed": bool(matching and self.expected_digest and matching[0]["digest"] != self.expected_digest)}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"available": False, "model_installed": False}
