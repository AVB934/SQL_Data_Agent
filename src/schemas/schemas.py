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


class FilteredSpec(DatabaseSchema):
    filtered_tables: list[TableSpec] = Field(default_factory=list)


class DataResultSpec(DatabaseSchema):
    query: str = Field(min_length=1)
    results: list[str] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)


class ReviewFilteredSpec(DatabaseSchema):
    filtered_tables: list[TableSpec] = Field(default_factory=list)
    review_status: Literal["approved", "pending", "rejected"] = Field(default="pending")


class ReviewDataResultSpec(DatabaseSchema):
    query: str = Field(min_length=1)
    results: list[str] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)
    review_status: Literal["approved", "pending", "rejected"] = Field(default="pending")
