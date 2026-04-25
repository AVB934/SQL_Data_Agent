# SQL_DATA_Agent\src\agents\baseline.py

from __future__ import annotations

import json
import re

from src.agents.base import BaseAgent
from src.config.prompts import (
    DATA_AGENT_PROMPT,
    DATA_AGENT_QUESTION,
    FILTER_AGENT_PROMPT,
    FILTER_AGENT_QUESTION,
    VERIFY_AGENT_PROMPT,
)
from src.LLM.gemini import GeminiClient
from src.schemas.schemas import (
    DataResultSpec,
    FilteredSpec,
    ReviewDataResultSpec,
    ReviewFilteredSpec,
)

# ---------------------------------------------------------------------------
# Filter Agent
# ---------------------------------------------------------------------------


class FilterAgent(BaseAgent):
    """
    Selects relevant tables for a given question.
    """

    def __init__(self, context, filter_prompt: str = FILTER_AGENT_PROMPT) -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.filter_prompt = filter_prompt

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, question: str) -> FilteredSpec:
        response = self.gemini_client.run(
            system_instruction=self.filter_prompt,
            question=self._build_filter_question(question),
        )
        relevant_names = self._parse_table_names(response)

        relevant = [
            t for t in self.context.updated_tables if t.table_name in relevant_names
        ]

        # Fallback: if the LLM returned names we couldn't match, use all tables
        if not relevant:
            relevant = self.context.updated_tables

        return FilteredSpec(filtered_tables=relevant)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_filter_question(self, question: str) -> str:
        """
        Serialises the available tables (name + columns + descriptions) into
        a concise block and fills the FILTER_AGENT_QUESTION template.
        The output format contract lives in FILTER_AGENT_PROMPT, not here.
        """
        table_summaries: list[str] = []

        for table in self.context.updated_tables:
            col_lines = []
            for col in table.columns:
                desc_text = ""
                for desc in table.column_descriptions:
                    if desc.column_name == col.name:
                        desc_text = f" — {desc.inferred_meaning}"
                        break
                col_lines.append(f"    - {col.name} ({col.dtype}){desc_text}")

            table_summaries.append(
                f"Table: {table.table_name}\n" + "\n".join(col_lines)
            )

        return FILTER_AGENT_QUESTION.format(
            tables_block="\n\n".join(table_summaries),
            question=question,
        )

    def _parse_table_names(self, response: str) -> list[str]:
        """
        Extracts the list of table names from the LLM JSON response.
        Falls back to an empty list if parsing fails, which triggers the
        fallback-to-all-tables path in run().
        """
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", response).strip()
            data = json.loads(cleaned)
            names = data.get("relevant_tables", [])
            if isinstance(names, list):
                return [str(n) for n in names]
        except (json.JSONDecodeError, AttributeError):
            pass

        return []


# ---------------------------------------------------------------------------
# Data Agent
# ---------------------------------------------------------------------------


class DataAgent(BaseAgent):
    """
    Generates and executes SQL queries.
    """

    def __init__(self, context, data_prompt: str = DATA_AGENT_PROMPT) -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.data_prompt = data_prompt

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, question: str, filtered_spec: FilteredSpec) -> DataResultSpec:
        db = self.context.metadata.get("db")

        if not db:
            raise RuntimeError("DataAgent: No database connection in context")

        response = self.gemini_client.run(
            system_instruction=self.data_prompt,
            question=self._build_data_question(question, filtered_spec),
        )
        query = self._parse_sql_query(response)

        cursor = db.connection.cursor()
        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()

        results_dict: list[dict] = [dict(zip(columns, row)) for row in rows]

        return DataResultSpec(
            query=query,
            results=results_dict,
            tables=filtered_spec.filtered_tables,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_data_question(self, question: str, filtered_spec: FilteredSpec) -> str:
        """
        Gives the LLM a full schema snapshot for every relevant table and
        fills the DATA_AGENT_QUESTION template.
        The output format contract lives in DATA_AGENT_PROMPT, not here.
        """
        table_blocks: list[str] = []

        for table in filtered_spec.filtered_tables:
            col_lines = [
                f"    - {c.name} ({c.dtype})"
                f"{' NOT NULL' if not c.is_nullable else ''}"
                for c in table.columns
            ]
            fk_lines = [
                f"    - {fk.column} → {fk.references_table}.{fk.references_column}"
                for fk in table.foreign_keys
            ]
            sample_lines = [f"    {json.dumps(row)}" for row in table.sample_rows[:3]]

            block = f"Table: {table.table_name}\n"
            block += "  Primary key: " + ", ".join(table.primary_key) + "\n"
            block += "  Columns:\n" + "\n".join(col_lines)
            if fk_lines:
                block += "\n  Foreign keys:\n" + "\n".join(fk_lines)
            if sample_lines:
                block += "\n  Sample rows:\n" + "\n".join(sample_lines)

            table_blocks.append(block)

        return DATA_AGENT_QUESTION.format(
            schema_block="\n\n".join(table_blocks),
            question=question,
        )

    def _parse_sql_query(self, response: str) -> str:
        """
        Extracts the SQL string from the LLM JSON response.
        Raises ValueError if parsing fails so the caller gets a clear
        signal rather than a silent bad query.
        """
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", response).strip()
            data = json.loads(cleaned)
            sql = data.get("sql", "").strip()
            if sql:
                return sql
        except (json.JSONDecodeError, AttributeError):
            pass

        raise ValueError(
            f"DataAgent: could not extract a SQL query from the LLM response.\n"
            f"Raw response:\n{response}"
        )


# ---------------------------------------------------------------------------
# Verify Agent
# ---------------------------------------------------------------------------


class VerifyAgent(BaseAgent):
    """
    Validates outputs before they proceed.
    """

    def __init__(self, context, verify_prompt: str = VERIFY_AGENT_PROMPT) -> None:
        super().__init__(context)
        self.gemini_client = GeminiClient()
        self.verify_prompt = verify_prompt

    def review_filtered(self, spec: FilteredSpec) -> ReviewFilteredSpec:
        if not spec.filtered_tables:
            raise ValueError(
                "VerifyAgent.review_filtered: received an empty filtered_tables list. "
                "This should have been caught upstream by FilteredSpec validation."
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
        raise NotImplementedError(
            "VerifyAgent.run() is not implemented. "
            "Use review_filtered() or review_data() directly."
        )
