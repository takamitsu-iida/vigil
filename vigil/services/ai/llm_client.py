"""LLM クライアント抽象化 — OpenAI / Ollama を切り替え。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def ask(self, prompt: str) -> str: ...


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI  # lazy import — optional dep
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def ask(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""


class OllamaClient(LLMClient):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3") -> None:
        import httpx  # already in deps
        self._client = httpx.Client(base_url=base_url, timeout=120.0)
        self._model = model

    def ask(self, prompt: str) -> str:
        resp = self._client.post(
            "/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def create_llm_client(
    provider: str = "openai",
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "llama3",
) -> LLMClient:
    if provider.lower() == "ollama":
        return OllamaClient(base_url=ollama_base_url, model=ollama_model)
    return OpenAIClient(api_key=openai_api_key, model=openai_model)
