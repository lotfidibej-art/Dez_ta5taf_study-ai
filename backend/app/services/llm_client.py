import json
import logging
import os
import random
import time
from typing import Any, Dict, Literal, Optional, Type, Union

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GeminiLLMClient:
    """Production client for Gemini LLM reasoning and agent evaluation.

    Encapsulates official google-genai Python SDK calls, strictly delegating
    all reasoning workloads to Google Cloud infrastructure with zero local weights.
    Includes exponential backoff retry logic for 429/503 resilience.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        fast_model: Optional[str] = None,
        reasoning_model: Optional[str] = None,
        max_retries: int = 3,
        base_backoff_sec: float = 1.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.fast_model = fast_model or os.getenv(
            "LLM_FAST_MODEL", "gemini-3.5-flash-lite"
        )
        self.reasoning_model = reasoning_model or os.getenv(
            "LLM_REASONING_MODEL", "gemini-3.8-flash"
        )
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

        self._client = None
        if self.api_key and self.api_key != "your_google_ai_studio_key_here":
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
                logger.info(
                    "GeminiLLMClient initialized (fast=%s, reasoning=%s)",
                    self.fast_model,
                    self.reasoning_model,
                )
            except Exception as e:
                logger.warning("Could not initialize google.genai client: %s", e)
        else:
            logger.warning(
                "GEMINI_API_KEY is unset or default placeholder. External LLM calls will fail until configured."
            )

    def _get_client(self):
        if self._client is None:
            from google import genai

            api_key = self.api_key or os.getenv("GEMINI_API_KEY")
            if not api_key or api_key == "your_google_ai_studio_key_here":
                raise ValueError(
                    "GEMINI_API_KEY environment variable is missing or using placeholder."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    def generate_structured(
        self,
        prompt: str,
        schema: Union[Type[BaseModel], Dict[str, Any]],
        tier: Literal["fast", "reasoning"] = "fast",
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Any:
        """Invokes Gemini model to produce validated, structured JSON responses.

        Includes exponential backoff retries on transient rate limits (429/503).

        Args:
            prompt: User/context instruction for the LLM.
            schema: Pydantic model class or JSON schema dict defining desired structure.
            tier: 'fast' for high-throughput feedback, 'reasoning' for complex pedagogy/diagnosis.
            system_instruction: Optional system instruction prompt.
            temperature: Sampling temperature (default 0.2 for deterministic grading/structuring).

        Returns:
            Parsed Pydantic instance or dictionary matching the schema.
        """
        client = self._get_client()
        from google.genai import types

        model_name = self.fast_model if tier == "fast" else self.reasoning_model

        config_kwargs: Dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
            "temperature": temperature,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config = types.GenerateContentConfig(**config_kwargs)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    "Dispatching LLM call to model=%s (tier=%s, attempt=%d)",
                    model_name,
                    tier,
                    attempt + 1,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )

                # Check if SDK parsed Pydantic schema
                if hasattr(response, "parsed") and response.parsed is not None:
                    return response.parsed

                # Fallback string parsing
                if response.text:
                    cleaned_text = response.text.strip()
                    if cleaned_text.startswith("```json"):
                        cleaned_text = cleaned_text[7:]
                    if cleaned_text.startswith("```"):
                        cleaned_text = cleaned_text[3:]
                    if cleaned_text.endswith("```"):
                        cleaned_text = cleaned_text[:-3]
                    data = json.loads(cleaned_text.strip())
                    if isinstance(schema, type) and issubclass(schema, BaseModel):
                        return schema.model_validate(data)
                    return data

                raise ValueError("Received empty response from Gemini API.")

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_transient = any(
                    err in err_str for err in ["429", "503", "resource_exhausted", "rate_limit", "quota"]
                )
                if is_transient and attempt < self.max_retries:
                    backoff = (self.base_backoff_sec * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Transient error (%s). Retrying in %.2fs (attempt %d/%d)...",
                        e,
                        backoff,
                        attempt + 1,
                        self.max_retries,
                    )
                    time.sleep(backoff)
                elif tier == "reasoning" and model_name != self.fast_model:
                    logger.warning(
                        "Reasoning model %s unavailable (%s). Gracefully falling back to %s...",
                        model_name,
                        e,
                        self.fast_model,
                    )
                    return self.generate_structured(
                        prompt=prompt,
                        schema=schema,
                        tier="fast",
                        system_instruction=system_instruction,
                        temperature=temperature,
                    )
                else:
                    raise last_error


_llm_client_instance: Optional[GeminiLLMClient] = None


def get_llm_client() -> GeminiLLMClient:
    """Accessor for global GeminiLLMClient instance."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = GeminiLLMClient()
    return _llm_client_instance
