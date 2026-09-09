"""Production Sarvam AI LLM Provider integration using httpx and Sarvam API specifications."""

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncGenerator

import httpx
from src.config.pricing import calculate_llm_cost
from src.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class SarvamLLMProvider(LLMProvider):
    """Sarvam AI (sarvam-105b) provider implementation with async HTTP, retries, and costs."""

    def __init__(
        self,
        api_key: str | None = None,
        api_endpoint: str = "https://api.sarvam.ai/v1/chat/completions",
        model: str = "sarvam-105b",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self.api_endpoint = api_endpoint
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
        return calculate_llm_cost(
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
        )

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is missing. Provide an API key or set MOCK_LLM=true.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.post(self.api_endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    data = response.json()

                    choice = data.get("choices", [{}])[0]
                    content = choice.get("message", {}).get("content") or ""
                    usage = data.get("usage", {})
                    p_tokens = usage.get("prompt_tokens", len(prompt.split()))
                    c_tokens = usage.get("completion_tokens", len(content.split()))
                    cost = self.calculate_cost(p_tokens, c_tokens)

                    return LLMResponse(
                        content=content,
                        model_name=self.model,
                        prompt_tokens=p_tokens,
                        completion_tokens=c_tokens,
                        total_tokens=p_tokens + c_tokens,
                        estimated_cost_usd=cost,
                        latency_ms=elapsed_ms,
                        finish_reason=choice.get("finish_reason", "stop"),
                        metadata={"correlation_id": correlation_id or "", "provider": "sarvam"},
                    )
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    logger.warning(f"Sarvam API attempt {attempt} failed: {e}")
                    if attempt == self.max_retries:
                        raise RuntimeError(
                            f"Sarvam AI API failed after {self.max_retries} attempts: {e}"
                        )
                    await asyncio.sleep(1.0 * (2 ** (attempt - 1)))

        raise RuntimeError("Sarvam API request unreachable.")

    async def astream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is missing. Provide an API key or set MOCK_LLM=true.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", self.api_endpoint, json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
