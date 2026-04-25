# SQL_DATA_Agent\src\LLM\usage_tracker.py

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

# Gemini 2.0 flash free tier limits (per day)
# Source: https://ai.google.dev/gemini-api/docs/rate-limits
FREE_TIER_LIMITS = {
    "requests_per_day": 1500,
    "input_tokens_per_day": 1_000_000,
}

USAGE_FILE = Path(".gemini_usage.json")


class UsageTracker:
    """
    Persists daily Gemini API usage to a local JSON file.
    Resets automatically when the date changes (free tier resets at midnight PT).
    """

    def __init__(self) -> None:
        self._data = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Call this after every successful Gemini API response."""
        self._data["requests"] += 1
        self._data["input_tokens"] += input_tokens
        self._data["output_tokens"] += output_tokens
        self._save()

    @property
    def requests(self) -> int:
        return self._data["requests"]

    @property
    def input_tokens(self) -> int:
        return self._data["input_tokens"]

    @property
    def output_tokens(self) -> int:
        return self._data["output_tokens"]

    def requests_pct(self) -> float:
        return self.requests / FREE_TIER_LIMITS["requests_per_day"]

    def tokens_pct(self) -> float:
        return self.input_tokens / FREE_TIER_LIMITS["input_tokens_per_day"]

    def is_near_limit(self, threshold: float = 0.80) -> bool:
        """Returns True if either metric exceeds the warning threshold."""
        return self.requests_pct() >= threshold or self.tokens_pct() >= threshold

    def is_exhausted(self, threshold: float = 0.98) -> bool:
        """Returns True if either metric is at/near 100%."""
        return self.requests_pct() >= threshold or self.tokens_pct() >= threshold

    def summary(self) -> dict:
        return {
            "date": self._data["date"],
            "requests": self.requests,
            "requests_limit": FREE_TIER_LIMITS["requests_per_day"],
            "requests_pct": round(self.requests_pct() * 100, 1),
            "input_tokens": self.input_tokens,
            "input_tokens_limit": FREE_TIER_LIMITS["input_tokens_per_day"],
            "tokens_pct": round(self.tokens_pct() * 100, 1),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        today = str(date.today())

        if USAGE_FILE.exists():
            try:
                data = json.loads(USAGE_FILE.read_text())
                # Reset if it's a new day
                if data.get("date") == today:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass

        # Fresh day or corrupt file — start clean
        return self._empty(today)

    def _save(self) -> None:
        USAGE_FILE.write_text(json.dumps(self._data, indent=2))

    @staticmethod
    def _empty(today: str) -> dict:
        return {
            "date": today,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
