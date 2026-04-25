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
        thinking_budget: int = 0,
    ) -> None:
        self.model_name = model
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client = genai.Client(api_key=self.api_key)
        self.usage = UsageTracker()

    def run(self, system_instruction: str, question: str, retries: int = 3) -> str:

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
        )

        for attempt in range(1, retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=question,
                    config=config,
                    # request_options={"timeout": 30},
                )

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
                if e.code == 429:
                    retry_after = self._parse_retry_delay(str(e)) or (attempt * 5)

                    if attempt == retries:
                        raise RuntimeError(
                            f"Gemini quota exhausted after {retries} attempts. "
                            "Wait until midnight Pacific time to reset, "
                            "or add billing at https://ai.dev/rate-limit."
                        ) from e

                    print(
                        f"Rate limited. Retrying in {retry_after}s (attempt {attempt}/{retries})..."
                    )

                    try:
                        self._interruptible_sleep(retry_after)
                    except KeyboardInterrupt:
                        print("\nRetry interrupted by user.")
                        raise

                else:
                    raise

        raise RuntimeError("Gemini call failed after all retries.")

    def _parse_retry_delay(self, error_message: str) -> float | None:
        match = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)s", error_message, re.IGNORECASE)
        return float(match.group(1)) if match else None

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        try:
            while time.monotonic() < end:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting immediately.")
            raise
