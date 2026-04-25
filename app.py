# SQL_DATA_Agent\app.py

import os

import streamlit as st
from dotenv import load_dotenv

from src.LLM.gemini import GeminiClient
from src.LLM.usage_tracker import UsageTracker
from src.main import Main

load_dotenv()

# ----------------------------
# SESSION STATE INIT
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "connected" not in st.session_state:
    st.session_state.connected = False

if "main_agent" not in st.session_state:
    st.session_state.main_agent = None


if "connection_feedback" not in st.session_state:
    st.session_state.connection_feedback = None  # ("success"|"error", message)

if "db_config" not in st.session_state:
    st.session_state.db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "weather_db",
        "user": os.getenv("POSTGRES_USERNAME", ""),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


# ----------------------------
# SIDEBAR — CONNECTION FORM
# ----------------------------
st.sidebar.title("Database Explorer")
st.sidebar.subheader("Connection")

with st.sidebar.form("db_connection_form"):
    host = st.text_input("Host", value=st.session_state.db_config["host"])
    port = st.number_input("Port", value=st.session_state.db_config["port"])
    database = st.text_input("Database", value=st.session_state.db_config["database"])
    user = st.text_input("User", value=st.session_state.db_config["user"])
    password = st.text_input(
        "Password",
        value=st.session_state.db_config["password"],
        type="password",
    )

    submitted = st.form_submit_button("Connect to DB")

if submitted:
    st.session_state.db_config = {
        "host": host,
        "port": int(port),
        "database": database,
        "user": user,
        "password": password,
    }

    try:

        if st.session_state.main_agent is not None:
            st.session_state.main_agent.disconnect()
            st.session_state.main_agent = None
            st.session_state.connected = False

        main_agent = Main()
        connected = main_agent.connect(**st.session_state.db_config)

        if connected:
            st.session_state.main_agent = main_agent
            st.session_state.connected = True

            st.session_state.messages = []

            st.session_state.connection_feedback = (
                "success",
                f"Connected to {database}@{host}",
            )
        else:
            st.session_state.connected = False
            st.session_state.connection_feedback = (
                "error",
                "Failed to connect to database.",
            )

    except Exception as e:
        st.session_state.connected = False
        st.session_state.connection_feedback = ("error", f"Connection error: {e}")


if st.session_state.connection_feedback:
    level, msg = st.session_state.connection_feedback
    if level == "success":
        st.sidebar.success(msg)
    else:
        st.sidebar.error(msg)

# persistent status indicator
st.sidebar.divider()
if st.session_state.connected:
    st.sidebar.success("● Connected")
else:
    st.sidebar.error("● Not connected")


# ----------------------------
# SIDEBAR — MODEL INFO
# ----------------------------
st.sidebar.divider()
st.sidebar.subheader("Model")
# BUG FIX 2: derive the model name from GeminiClient directly so the UI
# stays in sync if the default ever changes in gemini.py
st.sidebar.write(GeminiClient().model_name)

# ----------------------------
# SIDEBAR — API USAGE
# ----------------------------
st.sidebar.divider()
st.sidebar.subheader("Gemini API Usage (today)")

tracker = UsageTracker()
summary = tracker.summary()

# Requests bar
req_pct = summary["requests_pct"] / 100
st.sidebar.caption(f"Requests: {summary['requests']} / {summary['requests_limit']}")
st.sidebar.progress(
    min(req_pct, 1.0),
    text=f"{summary['requests_pct']}%",
)

# Token bar
tok_pct = summary["tokens_pct"] / 100
st.sidebar.caption(
    f"Input tokens: {summary['input_tokens']:,} / {summary['input_tokens_limit']:,}"
)
st.sidebar.progress(
    min(tok_pct, 1.0),
    text=f"{summary['tokens_pct']}%",
)

# Warning banners
if tracker.is_exhausted():
    st.sidebar.error("Quota nearly exhausted — requests will fail.")
elif tracker.is_near_limit():
    st.sidebar.warning("Approaching daily free tier limit (80%+).")
else:
    st.sidebar.success("Usage within limits.")

st.sidebar.caption("Resets daily at midnight Pacific time.")

# ----------------------------
# SIDEBAR — TABLE EXPLORER
# ----------------------------
st.sidebar.divider()
st.sidebar.subheader("Tables")

if st.session_state.connected and st.session_state.main_agent:
    for table in st.session_state.main_agent.tables:
        with st.sidebar.expander(table.table_name):
            for col in table.columns:
                st.write(f"{col.name} : {col.dtype}")
else:
    st.sidebar.caption("Connect to a database to explore tables.")


# ----------------------------
# MAIN CHAT AREA
# ----------------------------
st.title("SQL Data Agent")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # BUG FIX 5: use st.markdown — _format_answer returns a markdown table
        st.markdown(msg["content"])

        if msg.get("details"):
            with st.expander("View details"):
                details = msg["details"]
                st.markdown(f"**Verification status:** `{details['review_status']}`")

                if details.get("citations"):
                    st.markdown("**Citations:**")
                    for c in details["citations"]:
                        row_val = (
                            list(c["row_identifier"].values())[0]
                            if c["row_identifier"]
                            else "—"
                        )
                        st.write(
                            f"- `{c['table_name']}` — `{c['column_name']}` = `{row_val}`"
                        )

user_input = st.chat_input("Ask a question about your data...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    if st.session_state.connected and st.session_state.main_agent:
        with st.spinner("Processing your question..."):
            final_answer = st.session_state.main_agent.answer(user_input)

        if final_answer:
            response = final_answer.answer
            details = {
                "review_status": final_answer.review_status,
                "citations": [
                    {
                        "table_name": c.table_name,
                        "column_name": c.column_name,
                        "row_identifier": c.row_identifier,
                    }
                    for c in final_answer.citations
                ],
            }
        else:
            response = "Sorry, I could not process your question. Please try again."
            details = None

    else:
        response = "Please connect to a database first."
        details = None

    st.session_state.messages.append(
        {"role": "assistant", "content": response, "details": details}
    )

    st.rerun()
