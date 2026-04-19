from __future__ import annotations

from src.agents.base import BaseAgent
from src.LLM.gemini import GeminiClient
from src.schemas.schemas import (
    DataResultSpec,
    FilteredSpec,
    ReviewDataResultSpec,
    ReviewFilteredSpec,
    UpdatedTableSpec,
)


# Filter Agent
class FilterAgent(BaseAgent):
    """
    Selects relevant tables for a given question.
    """

    def __init__(self, context, filter_prompt: str = "") -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.filter_prompt = filter_prompt

    def run(self, question: str) -> FilteredSpec:
        """
        TODO: Replace keyword matching with LLM call:
            response = self.gemini_client.run(
                system_instruction=self.filter_prompt,
                question=self._build_filter_question(question),
            )
            relevant_names = self._parse_table_names(response)
            relevant = [t for t in self.context.updated_tables if t.table_name in relevant_names]
            return FilteredSpec(filtered_tables=relevant)
        """
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


# Data Agent


class DataAgent(BaseAgent):
    """
    Generates and executes SQL queries.
    """

    def __init__(self, context, data_prompt: str = "") -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.data_prompt = data_prompt

    def run(self, question: str, filtered_spec: FilteredSpec) -> DataResultSpec:
        db = self.context.metadata.get("db")

        if not db:
            print("DataAgent: No database connection in context")
            return DataResultSpec(
                query="", results=[], tables=[]
            )  # Return empty DataResultSpec, not None

        # TODO: replace with LLM-generated query
        query = "SELECT * FROM weather_data LIMIT 10"

        results = db.execute_query(query) or []

        # Convert tuples to dicts properly
        if results and filtered_spec.filtered_tables:
            cursor = db.connection.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            cursor.close()
            results_dict = [dict(zip(columns, row)) for row in results]
        else:
            results_dict = []

        return DataResultSpec(
            query=query,
            results=results_dict,
            tables=filtered_spec.filtered_tables,
        )


# Verify Agent


class VerifyAgent(BaseAgent):
    """
    Validates outputs before they proceed.
    """

    def __init__(self, context, verify_prompt: str = "") -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.verify_prompt = verify_prompt

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
