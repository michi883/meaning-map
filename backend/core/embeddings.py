from __future__ import annotations

import os

from openai import AsyncOpenAI


class GradientEmbeddingsClient:
    def __init__(self, api_key: str, model_id: str, base_url: str) -> None:
        if not api_key:
            raise ValueError("Missing GRADIENT_MODEL_ACCESS_KEY")
        self.model_id = model_id
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def from_env(cls) -> "GradientEmbeddingsClient":
        api_key = os.getenv("GRADIENT_MODEL_ACCESS_KEY", "").strip()
        model_id = os.getenv("GRADIENT_EMBEDDING_MODEL_ID", "text-embedding-3-small").strip()
        base_url = os.getenv("GRADIENT_BASE_URL", "https://inference.do-ai.run/v1/").strip()
        return cls(api_key=api_key, model_id=model_id, base_url=base_url)

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string."""
        response = await self._client.embeddings.create(
            model=self.model_id,
            input=text,
        )
        return response.data[0].embedding
