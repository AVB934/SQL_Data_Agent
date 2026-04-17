from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.schemas.schemas import (
    ColumnDescription,
    UpdatedTableSpec,
    TableSpec,
)


# =========================================================
# Shared Context (Pipeline State)
# =========================================================

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


# =========================================================
# Schema Agent
# =========================================================

class SchemaAgent(BaseAgent):
    """
    Responsible for enriching raw TableSpec into EnrichedTableSpec.

    This should be run ONCE per query lifecycle.
    """

    def run(self) -> list[UpdatedTableSpec]:
        updated_tables: list[UpdatedTableSpec] = []

        for table in self.context.raw_tables:
            column_descriptions: list[ColumnDescription] = []

            for col in table.columns:
                desc = ColumnDescription(
                    table_name=table.table_name,
                    column_name=col.name,
                    inferred_meaning=self._infer_column_meaning(col.name, table.table_name),
                    sample_values=[
                        str(row.get(col.name, "")) for row in table.sample_rows
                    ],
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
        return updated_tables

    # -----------------------------------------------------
    # Placeholder for LLM call
    # -----------------------------------------------------
    def _infer_column_meaning(self, column_name: str, table_name: str) -> str:
        # Replace with LLM later
        return f"{column_name} in {table_name}"