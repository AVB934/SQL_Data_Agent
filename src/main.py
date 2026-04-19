# SQL_DATA_Agent\src\main.py
# Prompts are defined in src/config/prompts.py
# All agents use GeminiClient with prompts to guide LLM behavior
# Agents: SchemaAgent, FilterAgent, DataAgent, VerifyAgent

from __future__ import annotations

from typing import Any, Optional

from src.agents.base import AgentContext, SchemaAgent
from src.agents.baseline import DataAgent, FilterAgent, VerifyAgent
from src.config.prompts import (
    DATA_AGENT_PROMPT,
    FILTER_AGENT_PROMPT,
    SCHEMA_AGENT_PROMPT,
    VERIFY_AGENT_PROMPT,
)
from src.db import Database
from src.schemas.schemas import (
    Citation,
    ColumnSpec,
    DataResultSpec,
    FinalAnswer,
    ForeignKey,
    TableSpec,
)


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

            # Load tables from database and convert to TableSpec
            self.tables = self._load_tables_from_database()

            print(f"Connected to {database}@{host}")
            print(f"Loaded {len(self.tables)} tables")

            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def _load_tables_from_database(self) -> list[TableSpec]:
        """
        Introspect database schema and convert to TableSpec objects.
        """
        if not self.db:
            return []

        try:
            # Get raw schema from database
            raw_tables = self.db.get_tables()

            table_specs = []
            for table_data in raw_tables:
                table_name = table_data["table_name"]

                # Get primary keys
                primary_keys = self._get_primary_keys(table_name)

                # Get foreign keys
                foreign_keys = self._get_foreign_keys(table_name)

                # Get sample rows
                sample_rows = self._get_sample_rows(table_name)

                # Convert columns to ColumnSpec
                columns = [
                    ColumnSpec(
                        name=col["name"],
                        dtype=col["type"],
                        is_nullable=col.get("nullable", True),
                    )
                    for col in table_data["columns"]
                ]

                # Create TableSpec
                table_spec = TableSpec(
                    table_name=table_name,
                    columns=columns,
                    primary_key=primary_keys,
                    foreign_keys=foreign_keys,
                    sample_rows=sample_rows,
                )

                table_specs.append(table_spec)

            return table_specs

        except Exception as e:
            print(f"Error loading tables from database: {e}")
            return []

    def _get_primary_keys(self, table_name: str) -> list[str]:
        """
        Get primary keys for a table using information_schema.
        Uses parameterized queries to prevent SQL injection.
        """
        if not self.db:
            return []

        try:
            query = """
                SELECT column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
            """
            results = self.db.execute_query(query, (table_name,))
            return [row[0] for row in results] if results else []
        except Exception as e:
            print(f"Error getting primary keys for {table_name}: {e}")
            return []

    def _get_foreign_keys(self, table_name: str) -> list[ForeignKey]:
        """
        Get foreign keys for a table using information_schema.
        Uses parameterized queries to prevent SQL injection.
        """
        if not self.db:
            return []

        try:
            query = """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS references_table,
                    ccu.column_name AS references_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu 
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
            """
            results = self.db.execute_query(query, (table_name,))

            foreign_keys = []
            if results:
                for col, ref_table, ref_col in results:
                    foreign_keys.append(
                        ForeignKey(
                            column=col,
                            references_table=ref_table,
                            references_column=ref_col,
                        )
                    )

            return foreign_keys
        except Exception as e:
            print(f"Error getting foreign keys for {table_name}: {e}")
            return []

    def _get_sample_rows(self, table_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Get sample rows from a table.
        Note: Table name cannot be parameterized, but we validate it exists first.
        """
        if not self.db or not self.db.connection:
            return []

        try:
            # Validate table exists in information_schema first (safe validation)
            validation_query = "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s"
            validation_result = self.db.execute_query(validation_query, (table_name,))

            if not validation_result:
                print(f"Table {table_name} not found in schema")
                return []

            # Safe to execute with table name since we validated it exists
            query = f"SELECT * FROM {table_name} LIMIT {limit}"

            cursor = self.db.connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()

            # Get column names from cursor description
            column_names = (
                [desc[0] for desc in cursor.description] if cursor.description else []
            )
            cursor.close()

            if not results or not column_names:
                return []

            # Convert rows to dictionaries
            sample_rows = [
                {col_name: value for col_name, value in zip(column_names, row)}
                for row in results
            ]

            return sample_rows
        except Exception as e:
            print(f"Error getting sample rows for {table_name}: {e}")
            return []

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

        # Initialize Context - ONCE for all agents
        self.context = AgentContext(self.tables)
        self.context.metadata["db"] = self.db  # Database connection for DataAgent

        # 1. SCHEMA AGENT

        schema_agent = SchemaAgent(self.context, SCHEMA_AGENT_PROMPT)
        enriched_tables = schema_agent.run()

        if not enriched_tables:
            print("Schema agent failed")
            return None

        print(f"Schema enriched: {len(enriched_tables)} tables")

        # 2. FILTER AGENT

        filter_agent = FilterAgent(self.context, FILTER_AGENT_PROMPT)
        filtered_spec = filter_agent.run(question)

        verify_agent = VerifyAgent(self.context, VERIFY_AGENT_PROMPT)
        review_filtered = verify_agent.review_filtered(filtered_spec)

        if review_filtered.review_status == "rejected":
            print(f"Filter rejected: {review_filtered.reason}")
            return None

        print(f"Filtered to {len(filtered_spec.filtered_tables)} tables")

        # 3. DATA AGENT

        data_agent = DataAgent(self.context, DATA_AGENT_PROMPT)
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

    # Need primary key to identify row

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
