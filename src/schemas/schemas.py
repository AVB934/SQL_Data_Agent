# SQL_DATA_Agent\src\schemas\schemas.py

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Base Schema


class DatabaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


# Core Table Representation


class ColumnSpec(DatabaseSchema):
    name: str = Field(min_length=1)
    dtype: str = Field(min_length=1)
    is_nullable: bool = True


class ForeignKey(DatabaseSchema):
    column: str = Field(min_length=1)
    references_table: str = Field(min_length=1)
    references_column: str = Field(min_length=1)


class TableSpec(DatabaseSchema):
    table_name: str = Field(min_length=1)
    columns: list[ColumnSpec] = Field(min_length=1)
    # column_types: list[str] = Field(min_length=1)
    primary_key: list[str] = Field(min_length=1)  # supports composite keys
    foreign_keys: list[ForeignKey] = Field(default_factory=list)

    # Each row is a dict: {column_name: value}
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


# Schema Agent Output


class ColumnDescription(DatabaseSchema):
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    inferred_meaning: str = Field(min_length=1)
    sample_values: list[str] = Field(default_factory=list)


class UpdatedTableSpec(TableSpec):
    column_descriptions: list[ColumnDescription] = Field(min_length=1)


# Filter Agent Output


class FilteredSpec(DatabaseSchema):
    filtered_tables: list[UpdatedTableSpec] = Field(min_length=1)


# Data Agent Output


class DataResultSpec(DatabaseSchema):
    # Pydantic v2 config (fixes Decimal JSON crash)
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={Decimal: lambda v: float(v)}
    )

    # executed SQL query
    query: str = Field(min_length=1)

    # list of rows (must be JSON-safe after conversion in DataAgent)
    results: list[dict[str, Any]] = Field(default_factory=list)

    # tables used for query generation
    tables: list[UpdatedTableSpec] = Field(min_length=1)


# Verify Agent Output


class ReviewFilteredSpec(DatabaseSchema):
    filtered_tables: list[UpdatedTableSpec] = Field(min_length=1)
    review_status: Literal["approved", "pending", "rejected"] = "pending"
    reason: str | None = None


class ReviewDataResultSpec(DatabaseSchema):
    query: str = Field(min_length=1)
    results: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[UpdatedTableSpec] = Field(min_length=1)

    review_status: Literal["approved", "pending", "rejected"] = "pending"

    reason: str = Field(default="")


# Citations (Traceability Layer)


class Citation(DatabaseSchema):
    source_file: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)

    # Deterministic row identification (e.g. {"order_id": 123})
    row_identifier: dict[str, Any] = Field(min_length=1)


# Final Answer


class FinalAnswer(DatabaseSchema):
    original_question: str = Field(min_length=1)
    answer: str = Field(min_length=1)

    citations: list[Citation] = Field(min_length=1)

    review_status: Literal["approved", "pending", "rejected"] = "pending"
