# SQL_DATA_Agent\src\agents\base.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.config.prompts import SCHEMA_AGENT_QUESTION
from src.LLM.gemini import GeminiClient
from src.schemas.schemas import (
    ColumnDescription,
    TableSpec,
    UpdatedTableSpec,
)


# Shared Context (Pipeline State)
class AgentContext:
    """
    Shared state passed across agents.

    Holds:
    - raw tables
    - enriched tables (after SchemaAgent)
    - intermediate outputs
    """

    def __init__(self, tables: list[TableSpec]) -> None:
        self.raw_tables = tables
        self.updated_tables: list[UpdatedTableSpec] = []

        # future extensibility
        self.metadata: dict[str, Any] = {}


# =========================================================
# Base Agent
# =========================================================


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    """

    def __init__(self, context: AgentContext) -> None:
        self.context = context

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """
        Execute the agent task.
        Must return a schema-defined output.
        """
        ...


# Schema Agent


class SchemaAgent(BaseAgent):
    """
    Responsible for enriching raw TableSpec into EnrichedTableSpec.

    This should be run ONCE per query lifecycle.
    """

    def __init__(self, context: AgentContext, schema_prompt: str = "") -> None:
        super().__init__(context)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.gemini_client = GeminiClient()
        self.schema_prompt = schema_prompt

    def run(self) -> list[UpdatedTableSpec]:
        self.logger.info(f"[SCHEMA][START] tables={len(self.context.raw_tables)}")

        updated_tables: list[UpdatedTableSpec] = []

        for table in self.context.raw_tables:
            self.logger.info(f"[SCHEMA][TABLE] {table.table_name}")
            self.logger.info(f"[SCHEMA][COLUMNS] {[col.name for col in table.columns]}")

            column_descriptions: list[ColumnDescription] = []

            for col in table.columns:
                sample_values = [
                    str(row.get(col.name, "")) for row in table.sample_rows
                ]

                self.logger.debug(
                    f"[SCHEMA][COLUMN INPUT] {table.table_name}.{col.name} "
                    f"dtype={col.dtype} samples={sample_values[:3]}"
                )

                inferred = self._infer_column_meaning(
                    column_name=col.name,
                    table_name=table.table_name,
                    dtype=col.dtype,
                    sample_values=sample_values,
                )

                self.logger.debug(
                    f"[SCHEMA][COLUMN OUTPUT] {table.table_name}.{col.name} → {inferred}"
                )

                desc = ColumnDescription(
                    table_name=table.table_name,
                    column_name=col.name,
                    inferred_meaning=inferred,
                    sample_values=sample_values,
                )

                column_descriptions.append(desc)

            updated = UpdatedTableSpec(
                table_name=table.table_name,
                columns=table.columns,
                primary_key=table.primary_key,
                foreign_keys=table.foreign_keys,
                sample_rows=table.sample_rows,
                column_descriptions=column_descriptions,
            )

            updated_tables.append(updated)

        self.context.updated_tables = updated_tables

        self.logger.info(f"[SCHEMA][END] enriched_tables={len(updated_tables)}")

        return updated_tables

    def _infer_column_meaning(
        self,
        column_name: str,
        table_name: str,
        dtype: str,
        sample_values: list[str],
    ) -> str:

        question = SCHEMA_AGENT_QUESTION.format(
            column_name=column_name,
            table_name=table_name,
            dtype=dtype,
            sample_values=", ".join(sample_values) if sample_values else "none",
        )

        self.logger.debug(
            f"[SCHEMA][LLM INPUT] {table_name}.{column_name} | dtype={dtype}"
        )

        try:
            response = self.gemini_client.run(
                system_instruction=self.schema_prompt,
                question=question,
            )

            cleaned = response.strip()

            self.logger.debug(
                f"[SCHEMA][LLM OUTPUT] {table_name}.{column_name} → {cleaned}"
            )

            # Optional contract check (since prompt requires 1 sentence)
            if not cleaned:
                self.logger.warning(
                    f"[SCHEMA][WARNING] Empty response for {table_name}.{column_name}"
                )

            return cleaned

        except Exception as e:
            self.logger.error(f"[SCHEMA][ERROR] {table_name}.{column_name} failed: {e}")
            return column_name
