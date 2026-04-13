from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.schemas import ColumnDescription, TableSpec


class BaseAgent(ABC):
    """
    Schema Agent — base for all agents.
    Reads 1 file at a time

    """

    def __init__(self, source_file: str, table: TableSpec) -> None:
        self.source_file = source_file
        self.table = table
        self.column_descriptions: list[ColumnDescription] = []

    @abstractmethod
    def run(self) -> object:
        """
        Every agent must implement run().
        Returns the agent's specific output schema.
        """
        ...
