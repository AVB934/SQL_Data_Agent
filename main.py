# SQL_DATA_Agent\main.py

import subprocess
import sys


def main():
    """
    Entry point for the SQL Data Agent.
    Launches the Streamlit frontend — all DB connection,
    querying, and agent logic is handled through app.py.
    """
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app.py"],
        check=True,
    )


if __name__ == "__main__":
    main()
