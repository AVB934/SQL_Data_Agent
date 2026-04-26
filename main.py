# SQL_DATA_Agent\main.py

import subprocess
import sys


def main():
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py"],
            check=True,
        )

    except KeyboardInterrupt:
        print("\n[INFO] Stopping application (Ctrl+C received). Goodbye!")

    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Streamlit exited with error: {e}")


if __name__ == "__main__":
    main()
