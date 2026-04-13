from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TableSpec(DatabaseSchema):
    table_name: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    column_types: list[str] = Field(min_length=1)
    primary_key: str = Field(min_length=1)
    foreign_keys: list[str] = Field(default_factory=list)
    sample_rows: list[list] = Field(default_factory=list)


# Schema Agent
class ColumnDescription(DatabaseSchema):
    column_name: str = Field(min_length=1)
    inferred_meaning: str = Field(min_length=1)
    sample_values: list[str] = Field(default_factory=list)


# Filter Agent
class FilteredSpec(DatabaseSchema):
    filtered_tables: list[TableSpec] = Field(default_factory=list)


# Data Agent
class DataResultSpec(DatabaseSchema):
    query: str = Field(min_length=1)  # SQL query executed
    results: list[str] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)


# Verify Agent
class ReviewFilteredSpec(DatabaseSchema):
    filtered_tables: list[TableSpec] = Field(default_factory=list)
    review_status: Literal["approved", "pending", "rejected"] = Field(default="pending")


class ReviewDataResultSpec(DatabaseSchema):
    query: str = Field(min_length=1)
    results: list[str] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)
    review_status: Literal["approved", "pending", "rejected"] = Field(default="pending")


# Citations
class Citation(DatabaseSchema):
    source_file: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    row_reference: str = Field(min_length=1)


class FinalAnswer(DatabaseSchema):
    original_question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
    review_status: Literal["approved", "pending", "rejected"] = Field(default="pending")
