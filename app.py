# build streamlit ui - first show message if connection successfull then  open chat window,
# after postgres details, in the chat window have user message, response, enter button, text boxs for questions, left side pane can have metadata
# left side pane of ui - model name,database,table names,and if you click table you get column names, and data types

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
    st.session_state.main_agent: Main | None = None

if "db_config" not in st.session_state:
    st.session_state.db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "weather_db",
        "user": os.getenv("POSTGRES_USERNAME", ""),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


# ----------------------------
# SIDEBAR (LEFT PANE)
# ----------------------------
st.sidebar.title("Database Explorer")

st.sidebar.subheader("Connection")

# Connection form
with st.sidebar.form("db_connection_form"):
    st.session_state.db_config["host"] = st.text_input(
        "Host", value=st.session_state.db_config["host"]
    )
    st.session_state.db_config["port"] = st.number_input(
        "Port", value=st.session_state.db_config["port"]
    )
    st.session_state.db_config["database"] = st.text_input(
        "Database", value=st.session_state.db_config["database"]
    )
    st.session_state.db_config["user"] = st.text_input(
        "User", value=st.session_state.db_config["user"]
    )
    st.session_state.db_config["password"] = st.text_input(
        "Password", value=st.session_state.db_config["password"], type="password"
    )

    if st.form_submit_button("Connect to DB"):
        try:
            main_agent = Main()
            connected = main_agent.connect(
                host=st.session_state.db_config["host"],
                port=st.session_state.db_config["port"],
                database=st.session_state.db_config["database"],
                user=st.session_state.db_config["user"],
                password=st.session_state.db_config["password"],
            )
            if connected:
                st.session_state.main_agent = main_agent
                st.session_state.connected = True
                st.success("Connected successfully!")
            else:
                st.error("Failed to connect to database")
        except Exception as e:
            st.error(f"Connection error: {str(e)}")

if st.session_state.connected:
    st.sidebar.success("Connected successfully")
else:
    st.sidebar.error("Not connected")


st.sidebar.divider()

st.sidebar.subheader("Model")
st.sidebar.write("gemini-2.0-flash")  # dynamic later


# ----------------------------
# DATABASE METADATA
# ----------------------------
db_schema = {}

if st.session_state.connected and st.session_state.main_agent:
    # Build schema from loaded tables
    for table in st.session_state.main_agent.tables:
        columns = {}
        for col in table.columns:
            columns[col.name] = col.type
        db_schema[table.table_name] = columns
else:
    # Mock schema for reference
    db_schema = {
        "users": {"id": "int", "name": "text", "email": "text"},
        "orders": {"order_id": "int", "user_id": "int", "amount": "float"},
    }


# ----------------------------
# TABLE EXPLORER
# ----------------------------
st.sidebar.subheader("Tables")

for table_name, columns in db_schema.items():
    with st.sidebar.expander(table_name):
        for col, dtype in columns.items():
            st.write(f"{col} : {dtype}")


# ----------------------------
# MAIN CHAT AREA
# ----------------------------
st.title("SQL Data Agent Chat")

# show chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])


# user input
user_input = st.chat_input("Ask a question about your data")

if user_input:
    # store user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Get response from Main agent
    if st.session_state.connected and st.session_state.main_agent:
        with st.spinner("Processing your question..."):
            final_answer = st.session_state.main_agent.answer(user_input)

            if final_answer:
                response = final_answer.answer
            else:
                response = "Sorry, I could not process your question. Please try again."
    else:
        response = "Please connect to the database first."

    st.session_state.messages.append({"role": "assistant", "content": response})

    st.rerun()
