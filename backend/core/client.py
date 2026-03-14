from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import AsyncOpenAI


class GradientLLMClient:
    def __init__(self, api_key: str, model_id: str, base_url: str) -> None:
        if not api_key:
            raise ValueError("Missing GRADIENT_MODEL_ACCESS_KEY")
        self.model_id = model_id
        self.base_url = base_url
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def from_env(cls) -> "GradientLLMClient":
        api_key = os.getenv("GRADIENT_MODEL_ACCESS_KEY", "").strip()
        model_id = os.getenv("GRADIENT_MODEL_ID", "openai-gpt-oss-120b").strip()
        base_url = os.getenv("GRADIENT_BASE_URL", "https://inference.do-ai.run/v1/").strip()
        return cls(api_key=api_key, model_id=model_id, base_url=base_url)

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_completion_tokens: int = 1200,
    ) -> dict[str, Any]:
        """Generate structured JSON from a chat completion with a parsing fallback."""
        response = await self._client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            response_format={"type": "json_object"},
        )

        content = (response.choices[0].message.content or "").strip()
        return self._extract_json(content)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        if not content:
            raise ValueError("Model returned empty content")
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Expected top-level JSON object")
            return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("Could not locate JSON object in model output")

        parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("Expected top-level JSON object")
        return parsed
