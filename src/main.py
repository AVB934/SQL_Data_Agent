from __future__ import annotations

from typing import Optional

from src.agents.base import AgentContext, SchemaAgent
from src.agents.baseline import FilterAgent, VerifyAgent, DataAgent
from src.db import Database
from src.schemas.schemas import (
    Citation,
    DataResultSpec,
    FinalAnswer,
    TableSpec,
)

# PROMPTS


SCHEMA_AGENT_PROMPT = """

"""

FILTER_AGENT_PROMPT = """

"""

DATA_AGENT_PROMPT = """

"""

VERIFY_AGENT_PROMPT = """

"""


class Main:

    def __init__(self):
        self.db: Optional[Database] = None
        self.tables: list[TableSpec] = []

        # shared execution context
        self.context: Optional[AgentContext] = None

    # DB CONNECTION

    def connect(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> bool:
        try:
            self.db = Database(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
            )
            self.db.connect()

            print(f"Connected to {database}@{host}")
            print(f"Loaded {len(self.tables)} tables")

            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if self.db:
            self.db.close()
            self.db = None
            print("Database connection closed")

    # MAIN EXECUTION
    def answer(self, question: str) -> Optional[FinalAnswer]:
        if not self.db:
            print("No database connection. Call connect() first.")
            return None

        if not self.tables:
            print("No tables loaded.")
            return None

        print(f"\nQuestion: {question}\n")

        # Initialize Context

        self.context = AgentContext(self.tables)

        # 1. SCHEMA AGENT

        schema_agent = SchemaAgent(self.context)
        enriched_tables = schema_agent.run()

        if not enriched_tables:
            print("Schema agent failed")
            return None

        print(f"Schema enriched: {len(enriched_tables)} tables")

        # 2. FILTER AGENT

        filter_agent = FilterAgent(self.context)
        filtered_spec = filter_agent.run(question)

        verify_agent = VerifyAgent(self.context)
        review_filtered = verify_agent.review_filtered(filtered_spec)

        if review_filtered.review_status == "rejected":
            print(f"Filter rejected: {review_filtered.reason}")
            return None

        print(f"Filtered to {len(filtered_spec.filtered_tables)} tables")

        # 3. DATA AGENT

        data_agent = DataAgent(self.context)
        data_result: DataResultSpec = data_agent.run(
            question,
            filtered_spec,
        )

        if not data_result:
            print("Data agent failed")
            return None

        print(f"Query executed, rows: {len(data_result.results)}")

        # 4. VERIFY DATA

        review_data = verify_agent.review_data(data_result)

        print(f"Verification status: {review_data.review_status}")

        # 5. CITATIONS

        citations = self._generate_citations(data_result)

        # 6. FINAL ANSWER

        final_answer = FinalAnswer(
            original_question=question,
            answer=self._format_answer(data_result),
            citations=citations,
            review_status=review_data.review_status,
        )

        print("\nDone\n")
        return final_answer

    # HELPERS

    def _generate_citations(
        self,
        data_result: DataResultSpec,
    ) -> list[Citation]:
        citations: list[Citation] = []

        for table in data_result.tables:
            for row in data_result.results:
                if not table.primary_key:
                    continue

                pk = table.primary_key[0]

                if pk not in row:
                    continue

                citation = Citation(
                    source_file="database",
                    table_name=table.table_name,
                    column_name=pk,
                    row_identifier={pk: row[pk]},
                )
                citations.append(citation)

        return citations

    def _format_answer(self, data_result: DataResultSpec) -> str:
        if not data_result.results:
            return "No results found."

        lines = [str(row) for row in data_result.results]

        return f"Query:\n{data_result.query}\n\nResults:\n" + "\n".join(lines)
