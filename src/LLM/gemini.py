# SQL_DATA_Agent\src\LLM\gemini.py

from __future__ import annotations

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.LLM.usage_tracker import UsageTracker

load_dotenv()


class GeminiClient:
    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        thinking_budget: int = 1024,
    ) -> None:
        self.model_name = model
        self.thinking_budget = thinking_budget
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client = genai.Client(api_key=self.api_key)

        # Shared tracker — same instance is reused across all agent calls
        self.usage = UsageTracker()

    def run(self, system_instruction: str, question: str, retries: int = 3) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
            ),
        )

        for attempt in range(1, retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=question,
                    config=config,
                )

                # Record usage from response metadata
                if response.usage_metadata:
                    self.usage.record(
                        input_tokens=response.usage_metadata.prompt_token_count or 0,
                        output_tokens=response.usage_metadata.candidates_token_count
                        or 0,
                    )

                if response.text is None:
                    raise ValueError(
                        f"Gemini returned no text for model '{self.model_name}'. "
                        "Response may have been blocked or empty."
                    )

                return response.text

            except errors.ClientError as e:
                if e.code == 429 or e.status == "RESOURCE_EXHAUSTED":
                    retry_after = self._parse_retry_delay(str(e)) or (attempt * 5)

                    if attempt == retries:
                        raise RuntimeError(
                            f"Gemini quota exhausted after {retries} attempts. "
                            "You may have hit your daily free tier limit — "
                            "wait until midnight Pacific time for it to reset, "
                            "or add billing at https://ai.dev/rate-limit."
                        ) from e

                    print(
                        f"Rate limited. Retrying in {retry_after}s "
                        f"(attempt {attempt}/{retries})..."
                    )
                    time.sleep(retry_after)
                else:
                    raise

        raise RuntimeError("Gemini call failed after all retries.")

    def _parse_retry_delay(self, error_message: str) -> float | None:
        match = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)s", error_message, re.IGNORECASE)
        return float(match.group(1)) if match else None
