# SQL_DATA_Agent\src\db\database.py
from __future__ import annotations

from typing import Any

import psycopg2


class Database:

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection: psycopg2.extensions.connection | None = None

    def connect(self) -> None:
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            print("Database connection successful")
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to {self.database}@{self.host}: {e}"
            )

    # AFTER
    def execute_query(
        self,
        query: str,
        params: tuple[Any, ...] | None = None,
    ) -> list[tuple[Any, ...]] | None:
        if not self.connection:
            raise ConnectionError("Database connection not established")

        try:
            with (
                self.connection.cursor() as cursor
            ):  # context manager closes cursor automatically
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            self.connection.rollback()  # rollback on any error
            print(f"Error executing query: {e}")
            return None

    def get_tables(self) -> list[dict[str, Any]]:
        """
        Returns all tables in the public schema with their columns and metadata.
        Structured for use in SQL agents / UI schema explorers.
        """

        if not self.connection:
            raise ConnectionError("Database connection not established")

        try:
            tables = []

            # Step 1: Get all tables
            table_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """

            with self.connection.cursor() as cursor:
                cursor.execute(table_query)
                table_names = cursor.fetchall()

            # Step 2: Get columns for each table
            column_query = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = %s
                ORDER BY ordinal_position
            """

            for (table_name,) in table_names:

                with self.connection.cursor() as cursor:
                    cursor.execute(column_query, (table_name,))
                    columns_raw = cursor.fetchall()

                columns = [
                    {
                        "name": col_name,
                        "type": data_type,
                        "nullable": (is_nullable == "YES"),
                    }
                    for col_name, data_type, is_nullable in columns_raw
                ]

                tables.append(
                    {
                        "table_name": table_name,
                        "columns": columns,
                    }
                )

            return tables

        except Exception as e:
            raise RuntimeError(f"Error introspecting database schema: {e}")

    def close(self) -> None:  # just add return type hint
        if self.connection:
            self.connection.close()
            self.connection = (
                None  # ← add this so .connection doesn't point to a closed object
            )
            print("Database connection closed")
