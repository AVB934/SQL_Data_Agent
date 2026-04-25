# SQL_DATA_Agent\src\agents\baseline.py

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import (
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
        self.logger = logging.getLogger(self.__class__.__name__)
        self.gemini_client = GeminiClient()
        self.filter_prompt = filter_prompt

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, question: str) -> FilteredSpec:
        self.logger.info(f"[FILTER][INPUT] question={question}")
        self.logger.info(
            f"[FILTER][AVAILABLE TABLES] {[t.table_name for t in self.context.updated_tables]}"
        )

        built_question = self._build_filter_question(question)
        self.logger.debug(f"[FILTER][PROMPT]\n{built_question}")

        response = self.gemini_client.run(
            system_instruction=self.filter_prompt,
            question=built_question,
        )

        self.logger.info(f"[FILTER][LLM OUTPUT] {response}")

        relevant_names = self._parse_table_names(response)
        self.logger.info(f"[FILTER][PARSED TABLE NAMES] {relevant_names}")

        relevant = [
            t for t in self.context.updated_tables if t.table_name in relevant_names
        ]

        if not relevant:
            self.logger.warning("[FILTER] No match → fallback to all tables")
            relevant = self.context.updated_tables

        self.logger.info(f"[FILTER][OUTPUT TABLES] {[t.table_name for t in relevant]}")

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
    Generates and executes SQL queries with deep type diagnostics.
    """

    def __init__(self, context, data_prompt: str):
        super().__init__(context)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.gemini_client = GeminiClient()
        self.data_prompt = data_prompt

    # ------------------------------------------------------------
    # NORMALIZATION (CRITICAL DEBUG POINT)
    # ------------------------------------------------------------
    def _normalize(self, obj: Any, path: str = "root") -> Any:
        """
        Converts unsafe DB types (Decimal, datetime, etc.) into JSON-safe types.
        Fully traced so we know EXACTLY where Decimal originates.
        """

        if isinstance(obj, list):
            self.logger.debug(f"[NORMALIZE][LIST] {path} len={len(obj)}")
            return [self._normalize(v, f"{path}[{i}]") for i, v in enumerate(obj)]

        if isinstance(obj, dict):
            self.logger.debug(f"[NORMALIZE][DICT] {path} keys={list(obj.keys())}")
            return {k: self._normalize(v, f"{path}.{k}") for k, v in obj.items()}

        if isinstance(obj, Decimal):
            self.logger.warning(
                f"[NORMALIZE][DECIMAL FOUND] path={path} value={obj} type={type(obj)}"
            )
            return float(obj)

        return obj

    # ------------------------------------------------------------
    # RAW TYPE INSPECTION (BEFORE NORMALIZATION)
    # ------------------------------------------------------------
    def _inspect_raw_rows(self, columns, rows):
        self.logger.info("[RAW INSPECTION] scanning DB output types...")

        for i, row in enumerate(rows[:10]):
            for col, value in zip(columns, row):
                if isinstance(value, Decimal):
                    self.logger.error(
                        f"[RAW DECIMAL DETECTED] row={i} column={col} value={value}"
                    )

        self.logger.info("[RAW INSPECTION COMPLETE]")

    # ------------------------------------------------------------
    # FINAL INSPECTION (AFTER NORMALIZATION)
    # ------------------------------------------------------------
    def _inspect_final_rows(self, rows: list[dict[str, Any]]):
        self.logger.info("[FINAL INSPECTION] checking JSON safety...")

        for i, row in enumerate(rows[:5]):
            for k, v in row.items():
                try:
                    json.dumps(v)  # THIS is where your crash would happen
                except TypeError as e:
                    self.logger.critical(
                        f"[SERIALIZATION FAIL] row={i} column={k} value={v} type={type(v)} error={e}"
                    )

        self.logger.info("[FINAL INSPECTION COMPLETE]")

    # ------------------------------------------------------------
    # MAIN PIPELINE
    # ------------------------------------------------------------
    def run(self, question: str, filtered_spec: FilteredSpec) -> DataResultSpec:
        db = self.context.metadata.get("db")

        if not db:
            raise RuntimeError("No DB connection")

        self.logger.info(f"[DATA][INPUT] {question}")
        self.logger.info(
            f"[DATA][TABLES] {[t.table_name for t in filtered_spec.filtered_tables]}"
        )

        # LLM → SQL
        response = self.gemini_client.run(
            system_instruction=self.data_prompt,
            question=question,
        )

        self.logger.info(f"[DATA][LLM OUTPUT] {response}")

        query = json.loads(response)["sql"]
        self.logger.info(f"[DATA][SQL] {query}")

        # EXECUTE SQL
        cursor = db.connection.cursor()

        try:
            cursor.execute(query)

            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()

            self.logger.info(f"[DATA][ROWS] fetched={len(rows)}")
            self.logger.info(f"[DATA][COLUMNS] {columns}")

            # 🔥 CRITICAL: RAW inspection BEFORE ANY conversion
            self._inspect_raw_rows(columns, rows)

        finally:
            cursor.close()

        # CONVERT ROWS
        results_dict = [
            self._normalize(dict(zip(columns, row)), path=f"row[{i}]")
            for i, row in enumerate(rows)
        ]

        # FINAL SAFETY CHECK
        self._inspect_final_rows(results_dict)

        # FINAL LOG BEFORE RETURN
        try:
            json.dumps(results_dict)  # hard validation
            self.logger.info("[DATA] JSON SERIALIZATION OK")
        except Exception as e:
            self.logger.critical(f"[DATA] STILL BROKEN JSON: {e}")
            raise

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
        import json
        import re

        self.logger.info(f"[DATA][RAW RESPONSE]\n{response}")

        try:
            # remove ```json and ```
            cleaned = re.sub(r"```(?:json)?|```", "", response).strip()

            self.logger.debug(f"[DATA][CLEANED RESPONSE]\n{cleaned}")

            data = json.loads(cleaned)

            sql = data.get("sql", "").strip()

            if not sql:
                raise ValueError("Empty SQL returned from LLM")

            return sql

        except json.JSONDecodeError as e:
            self.logger.error(f"[DATA][JSON PARSE FAILED] {e}")
            self.logger.error(f"[DATA][RAW]\n{response}")
            raise


# ---------------------------------------------------------------------------
# Verify Agent
# ---------------------------------------------------------------------------


class VerifyAgent(BaseAgent):
    """
    Validates outputs before they proceed.
    """

    def __init__(self, context, verify_prompt: str = VERIFY_AGENT_PROMPT) -> None:
        super().__init__(context)
        self.logger = logging.getLogger(self.__class__.__name__)
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
        self.logger.info(f"[VERIFY][INPUT QUERY] {data.query}")
        self.logger.info(f"[VERIFY][RESULT COUNT] {len(data.results)}")

        if not data.results:
            self.logger.warning("[VERIFY] Rejected: No results returned")
            return ReviewDataResultSpec(
                query=data.query,
                results=data.results,
                tables=data.tables,
                review_status="rejected",
                reason="No results returned",
            )

        for row in data.results:
            if not isinstance(row, dict):
                self.logger.error(f"[VERIFY] Invalid row type: {type(row)}")
                return ReviewDataResultSpec(
                    query=data.query,
                    results=data.results,
                    tables=data.tables,
                    review_status="rejected",
                    reason="Invalid row format",
                )

        self.logger.info("[VERIFY] Approved")

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
