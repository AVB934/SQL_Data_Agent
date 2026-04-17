from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent, AgentContext
from src.schemas.schemas import (
    DataResultSpec,
    FilteredSpec,
    ReviewDataResultSpec,
    ReviewFilteredSpec,
    UpdatedTableSpec,
)


# =========================================================
# Filter Agent
# =========================================================

class FilterAgent(BaseAgent):
    """
    Selects relevant tables for a given question.
    """

    def run(self, question: str) -> FilteredSpec:
        relevant_tables: list[UpdatedTableSpec] = []

        question_lower = question.lower()

        for table in self.context.updated_tables:
            # Simple heuristic: table name match
            if table.table_name.lower() in question_lower:
                relevant_tables.append(table)
                continue

            # Column match
            for col in table.columns:
                if col.name.lower() in question_lower:
                    relevant_tables.append(table)
                    break

        # fallback: if nothing matched, return all tables
        if not relevant_tables:
            relevant_tables = self.context.updated_tables

        return FilteredSpec(filtered_tables=relevant_tables)


# =========================================================
# Data Agent
# =========================================================

class DataAgent(BaseAgent):
    """
    Executes data operations.

    NOTE: This is a baseline stub (no real SQL execution yet).
    """

    def run(self, question: str, filtered_spec: FilteredSpec) -> DataResultSpec:
        tables = filtered_spec.filtered_tables

        # Placeholder "query"
        query = f"-- simulated query for: {question}"

        results: list[dict[str, Any]] = []

        # naive: return sample rows from first table
        if tables:
            first_table = tables[0]
            results = first_table.sample_rows[:5]

        return DataResultSpec(
            query=query,
            results=results,
            tables=tables,
        )


# =========================================================
# Verify Agent
# =========================================================

class VerifyAgent(BaseAgent):
    """
    Validates outputs before they proceed.
    """

    def review_filtered(self, spec: FilteredSpec) -> ReviewFilteredSpec:
        if not spec.filtered_tables:
            return ReviewFilteredSpec(
                filtered_tables=[],
                review_status="rejected",
                reason="No tables selected",
            )

        return ReviewFilteredSpec(
            filtered_tables=spec.filtered_tables,
            review_status="approved",
        )

    def review_data(self, data: DataResultSpec) -> ReviewDataResultSpec:
        if not data.results:
            return ReviewDataResultSpec(
                query=data.query,
                results=data.results,
                tables=data.tables,
                review_status="rejected",
                reason="No results returned",
            )

        # Basic structural validation
        for row in data.results:
            if not isinstance(row, dict):
                return ReviewDataResultSpec(
                    query=data.query,
                    results=data.results,
                    tables=data.tables,
                    review_status="rejected",
                    reason="Invalid row format",
                )

        return ReviewDataResultSpec(
            query=data.query,
            results=data.results,
            tables=data.tables,
            review_status="approved",
        )
    
    def run(self, *args, **kwargs):

        return None