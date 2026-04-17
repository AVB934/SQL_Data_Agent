import psycopg2
from src.schemas.schemas import TableSpec


class Database:
    def __init__(self, host, port, database, user, password):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
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
            print(f"Error connecting to database: {e}")

    def close(self):
        if self.connection:
            self.connection.close()
            print("Database connection closed")

 

    