# SQL_DATA_Agent\src\LLM\gemini.py
# gemini.py should have .run or .answer - it will take def run(self,system instruction,question) then use self.model so self.model.run() and we can configure thinking level
# prompts in main file need to use gemini.py to run

from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class GeminiClient:
    """
    Thin wrapper around the Google Gemini API.

    Centralises all LLM calls so that:
    - The underlying model can be swapped in one place
    - Thinking budget is configured consistently
    - Prompt structure (system instruction + question) is standardised
    """

    def __init__(
        self,
        model: str = "gemini-3.0-flash",
        thinking_budget: int = 1024,
    ) -> None:

        self.model_name = model
        self.thinking_budget = thinking_budget
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client = genai.Client(api_key=self.api_key)

    def run(self, system_instruction: str, question: str) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
            ),
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=question,
            config=config,
        )

        if response.text is None:
            raise ValueError(
                f"Gemini returned no text for model '{self.model_name}'. "
                "Response may have been blocked or empty."
            )

        return response.text
