"""LLM wrapper with disk cache, retry, and JSON validation."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from crm_copilot.config import settings

T = TypeVar("T", bound=BaseModel)


class CachedLLMClient:
    """OpenAI client wrapper with disk cache, retry, and JSON validation."""

    def __init__(self) -> None:
        self.client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
        self.cache_dir = Path(settings.CACHE_DIR) / "llm_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, model: str, messages: list[dict[str, str]]) -> str:
        """Generate a cache key from model and messages."""
        content = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached(self, key: str) -> str | None:
        """Get cached response if exists."""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return data.get("response")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def _save_cache(self, key: str, response: str) -> None:
        """Save response to cache."""
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps({"response": response}))

    def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        model: str | None = None,
        max_retries: int = 2,
    ) -> T:
        """
        Call LLM with JSON schema, validate with Pydantic, retry once on validation error.

        Args:
            system: System prompt
            user: User prompt
            schema: Pydantic model class to validate response
            model: Model override (defaults to settings.LLM_MODEL)
            max_retries: Max retries for validation errors

        Returns:
            Validated Pydantic model instance
        """
        model = model or settings.LLM_MODEL
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        # Check cache
        cache_key = self._cache_key(model, messages)
        cached = self._get_cached(cache_key)
        if cached is not None:
            try:
                return schema.model_validate_json(cached)
            except ValidationError:
                pass  # Fall through to re-call

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from LLM")

                # Validate JSON with Pydantic
                validated = schema.model_validate_json(content)

                # Cache successful response
                self._save_cache(cache_key, content)
                return validated

            except ValidationError as e:
                last_error = e
                if attempt < max_retries:
                    # Add validation error to user message and retry
                    messages.append({"role": "assistant", "content": content or ""})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Validation error: {e}. "
                            "Please fix and return valid JSON matching the schema."
                        ),
                    })
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

            except Exception as e:
                # Retry on 429/5xx errors
                error_str = str(e)
                retryable = (
                    "429" in error_str
                    or "500" in error_str
                    or "502" in error_str
                    or "503" in error_str
                    or "504" in error_str
                )
                if attempt < max_retries and retryable:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise

        # Should not reach here, but for type checker
        raise last_error or RuntimeError("LLM call failed")


# Global instance
_llm_client: CachedLLMClient | None = None


def get_llm_client() -> CachedLLMClient:
    """Get or create the global LLM client."""
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = CachedLLMClient()
    return _llm_client


def complete_json(
    system: str,
    user: str,
    schema: type[T],
    model: str | None = None,
) -> T:
    """Convenience function for LLM JSON completion."""
    return get_llm_client().complete_json(system, user, schema, model)