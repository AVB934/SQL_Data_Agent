#SQL_DATA_Agent\main.py

import os

from dotenv import load_dotenv

from src.db import Database


def main():
    
    load_dotenv()

    # Create a database connection
    db = Database(
        host="localhost",
        port=5432,
        database="weather_db",
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    db.connect()

    # Execute a query
    result = db.execute_query("SELECT * FROM weather_data;")
    print(result)

    # Close the database connection
    db.close()


if __name__ == "__main__":
    main()


