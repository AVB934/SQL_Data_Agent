# SQL_DATA_Agent\src\LLM\gemini.py

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel

load_dotenv()


class GeminiClient:

    def __init__(self, model: str = "gemini-2.0-flash"):
        """
        Initialize Gemini client.

        Args:
            model: Model name to use (default: "gemini-2.0-flash")
        """
        self.model_name = model
        self.api_key = os.getenv("GEMINI_API_KEY")

        configure(api_key=self.api_key)
        self.model = GenerativeModel(model)
