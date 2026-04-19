# build streamlit ui - first show message if connection successfull then  open chat window,
# after postgres details, in the chat window have user message, response, enter button, text boxs for questions, left side pane can have metadata
# left side pane of ui - model name,database,table names,and if you click table you get column names, and data types

# SQL_DATA_Agent\app.py

import os

import streamlit as st
from dotenv import load_dotenv

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
    st.session_state.main_agent = None  # Main | None

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
    # use local variables — only write to session_state on submit
    host = st.text_input("Host", value=st.session_state.db_config["host"])
    port = st.number_input("Port", value=st.session_state.db_config["port"])
    database = st.text_input("Database", value=st.session_state.db_config["database"])
    user = st.text_input("User", value=st.session_state.db_config["user"])
    password = st.text_input(
        "Password",
        value=st.session_state.db_config["password"],
        type="password",
    )

    if st.form_submit_button("Connect to DB"):
        # write to session_state only after submit, not on every render
        st.session_state.db_config = {
            "host": host,
            "port": int(port),
            "database": database,
            "user": user,
            "password": password,
        }

        try:
            main_agent = Main()
            connected = main_agent.connect(**st.session_state.db_config)

            if connected:
                st.session_state.main_agent = main_agent
                st.session_state.connected = True
                st.success("Connected successfully!")
            else:
                st.session_state.connected = False
                st.error("Failed to connect to database")

        except Exception as e:
            st.session_state.connected = False
            st.error(f"Connection error: {str(e)}")


# connection status indicator
if st.session_state.connected:
    st.sidebar.success("Connected")
else:
    st.sidebar.error("Not connected")


# ----------------------------
# SIDEBAR — MODEL INFO
# ----------------------------
st.sidebar.divider()
st.sidebar.subheader("Model")
st.sidebar.write("gemini-2.0-flash")


# ----------------------------
# SIDEBAR — TABLE EXPLORER
# ----------------------------
st.sidebar.divider()
st.sidebar.subheader("Tables")

if st.session_state.connected and st.session_state.main_agent:
    # build schema from live loaded tables
    for table in st.session_state.main_agent.tables:
        with st.sidebar.expander(table.table_name):
            for col in table.columns:
                st.write(f"{col.name} : {col.dtype}")  # col.dtype not col.type
else:
    # placeholder when not connected
    st.sidebar.caption("Connect to a database to explore tables.")


# ----------------------------
# MAIN CHAT AREA
# ----------------------------
st.title("SQL Data Agent")

# show full chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        # re-render detail expanders from history if present
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


# user input
user_input = st.chat_input("Ask a question about your data...")

if user_input:
    # add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})

    if st.session_state.connected and st.session_state.main_agent:
        with st.spinner("Processing your question..."):
            final_answer = st.session_state.main_agent.answer(user_input)

        if final_answer:
            response = final_answer.answer

            # store details so they survive rerenders
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

    # add assistant message with optional details
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response,
            "details": details,
        }
    )

    st.rerun()
