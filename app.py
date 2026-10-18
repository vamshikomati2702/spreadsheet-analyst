"""Streamlit UI.  Run with:  streamlit run app.py"""

import streamlit as st

import agent

MAX_QUESTIONS = 5          # questions allowed per browser session
MAX_QUESTION_CHARS = 300
PLACEHOLDER_KEY = "paste-your-key-here"

st.set_page_config(page_title="Spreadsheet Analyst")
st.title("Spreadsheet Analyst")
st.write("Upload a CSV and ask questions about it in plain English. "
         "The AI writes and runs SQL on your data and explains the result.")
st.info("Your file is sent to an AI model for analysis and isn't stored. "
        "Don't upload sensitive data.")

# Check the API key early so the user gets a clear message, not a crash later.
try:
    if agent.get_api_key() == PLACEHOLDER_KEY:
        raise RuntimeError("placeholder")
except Exception:
    st.error("No API key found. Put your key in `.streamlit/secrets.toml` "
             "(ANTHROPIC_API_KEY = \"...\") and restart the app.")
    st.stop()

# Session state: remembers things between reruns (Streamlit reruns the script on every click).
st.session_state.setdefault("questions_used", 0)
st.session_state.setdefault("source", None)       # "sample" or "upload"
st.session_state.setdefault("last_upload_id", None)

# ---- 1. Pick a file: upload one, or use the sample ------------------------
uploaded = st.file_uploader("Upload a CSV file (max 10 MB)", type="csv")
if st.button("Try sample data"):
    st.session_state.source = "sample"
if uploaded is not None and uploaded.file_id != st.session_state.last_upload_id:
    st.session_state.last_upload_id = uploaded.file_id   # a new upload wins over the sample
    st.session_state.source = "upload"

if st.session_state.source is None:
    st.write("Upload a CSV or click **Try sample data** to get started.")
    st.stop()

# Load the data into DuckDB only when the file changes.
file_key = ("sample",) if st.session_state.source == "sample" else ("upload", uploaded.file_id)
if st.session_state.get("file_key") != file_key:
    try:
        if st.session_state.source == "sample":
            st.session_state.con = agent.load_csv("sample.csv")
        else:
            st.session_state.con = agent.load_csv(uploaded.getvalue())
    except Exception as e:
        st.error(f"Could not load the file: {e}")
        st.session_state.source = None
        st.stop()
    st.session_state.file_key = file_key
con = st.session_state.con

st.subheader("Preview (first 5 rows)")
st.dataframe(con.execute("SELECT * FROM data LIMIT 5").df(), hide_index=True)

# ---- 2. Ask a question -----------------------------------------------------
left = MAX_QUESTIONS - st.session_state.questions_used
question = st.text_area("Your question", max_chars=MAX_QUESTION_CHARS,
                        placeholder="e.g. How many tickets are there per plan?")
ask = st.button("Ask", disabled=(left <= 0))
caption = st.empty()   # placeholder, so the count can be refreshed after the agent runs
caption.caption(f"{left} of {MAX_QUESTIONS} questions left in this session.")
if left <= 0:
    st.warning("You've used all your questions for this session.")

if ask and question.strip():
    st.session_state.questions_used += 1   # count it before running, so failures can't be retried for free

    # Show each step live while the agent works.
    def show_step(tool_name, tool_input, short_result):
        st.markdown(f"**{tool_name}**")
        if tool_input.get("query"):
            st.code(tool_input["query"], language="sql")
        if tool_name != "finish":
            st.text(short_result)

    with st.status("Analysing your data...", expanded=True) as status:
        try:
            result = agent.run_agent(con, question.strip(), on_step=show_step)
            status.update(label="Done", state="complete", expanded=False)
        except Exception as e:
            result = None
            status.update(label="Failed", state="error")
            st.error(f"Something went wrong: {e}")

    # ---- 3. Show the answer and the queries behind it ----------------------
    if result:
        st.subheader("Answer")
        st.markdown(result["answer"])
        queries = [s["input"]["query"] for s in result["steps"] if s["tool"] == "run_sql"]
        with st.expander("Queries used - check them yourself"):
            if queries:
                for i, q in enumerate(queries, 1):
                    st.markdown(f"**Query {i}**")
                    st.code(q, language="sql")
            else:
                st.write("No queries were run.")
    caption.caption(f"{MAX_QUESTIONS - st.session_state.questions_used} of {MAX_QUESTIONS} questions left in this session.")
