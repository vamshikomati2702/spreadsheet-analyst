"""Spreadsheet Analyst - the agent: a hand-written tool-use loop.

How it works (read this first):
1. We send the user's question + the tool list to Claude.
2. Claude replies with text and/or "tool_use" blocks (requests to run a tool).
3. We run each tool in Python and send the results back.
4. Repeat until Claude calls the `finish` tool (that is the final answer).
"""

import io
import os
import threading
from pathlib import Path

import anthropic
import duckdb
import pandas as pd

MODEL = "claude-sonnet-5-5"   # change the model here
MAX_TOKENS = 2000
MAX_STEPS = 8                 # safety limit so the loop can never run forever
MAX_ROWS = 50                 # most rows a query result may send back to Claude
MAX_CELL_CHARS = 200          # long cell text is cut to keep results small
MAX_FILE_BYTES = 10 * 1024 * 1024   # reject CSVs over 10 MB
SQL_TIMEOUT_SECONDS = 10
MEMORY_LIMIT = "512MB"        # a query that needs more fails instead of eating your RAM
SHORT_RESULT_CHARS = 300      # size of the result preview given to on_step

# The system prompt lives in guidelines.md (next to this file).
GUIDELINES = (Path(__file__).parent / "guidelines.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- API key
def get_api_key():
    """Read the key from the environment, or from Streamlit secrets."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        raise RuntimeError(
            "No API key found. Set the ANTHROPIC_API_KEY environment variable "
            "(or add it to .streamlit/secrets.toml)."
        )


# ------------------------------------------------------------ data loading
def load_csv(file):
    """Load a CSV into an in-memory DuckDB table called `data`.

    `file` can be a path (str / Path) or an uploaded file object / bytes.
    """
    # Get the raw bytes and check the size first.
    if isinstance(file, (str, Path)):
        if os.path.getsize(file) > MAX_FILE_BYTES:
            raise ValueError("File is over 10 MB. Please upload a smaller CSV.")
        raw = Path(file).read_bytes()
    else:
        raw = file if isinstance(file, bytes) else file.read()
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("File is over 10 MB. Please upload a smaller CSV.")

    df = pd.read_csv(io.BytesIO(raw))

    con = duckdb.connect(":memory:")
    con.register("loaded_df", df)
    con.execute("CREATE TABLE data AS SELECT * FROM loaded_df")
    con.unregister("loaded_df")

    # Lock the database down: no file/network access, limited memory, and
    # settings can't be changed back afterwards.
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute("SET enable_external_access=false")
    con.execute("SET lock_configuration=true")
    return con


# ------------------------------------------------------------------ tools
def format_rows(columns, rows):
    """Turn query results into a simple text table for Claude to read."""
    def cell(v):
        s = str(v)
        return s if len(s) <= MAX_CELL_CHARS else s[:MAX_CELL_CHARS] + "..."
    lines = [" | ".join(columns)]
    lines += [" | ".join(cell(v) for v in row) for row in rows]
    return "\n".join(lines)


def describe_table(con):
    """Column names, types, row count, and 5 sample rows."""
    cols = con.execute("DESCRIBE data").fetchall()
    count = con.execute("SELECT COUNT(*) FROM data").fetchone()[0]
    sample = con.execute("SELECT * FROM data LIMIT 5")
    names = [d[0] for d in sample.description]
    out = f"Table `data`: {count} rows\nColumns:\n"
    out += "\n".join(f"- {c[0]} ({c[1]})" for c in cols)
    out += "\n\nSample rows:\n" + format_rows(names, sample.fetchall())
    return out


def check_sql(con, query):
    """Return an error message if the query is not ONE SELECT/WITH statement, else None.

    We ask DuckDB's own parser instead of searching the text ourselves. A text
    search can be fooled by tricks like $$quoted$$ strings or comments that
    hide a second statement; the parser sees exactly what DuckDB would run.
    """
    try:
        statements = con.extract_statements(query)
    except Exception as e:
        return f"Could not parse the query: {e}"
    if len(statements) != 1:
        return "Only one statement is allowed."
    # A "WITH ... SELECT" counts as SELECT; "WITH ... DELETE" counts as DELETE.
    if statements[0].type != duckdb.StatementType.SELECT:
        return "Only SELECT (or WITH ... SELECT) statements are allowed."
    # DuckDB rewrites a few commands (like PRAGMA) into SELECTs, so also check
    # the first word the user actually typed (comments are skipped by the tokenizer).
    tokens = duckdb.tokenize(query)
    end = tokens[1][0] if len(tokens) > 1 else len(query)
    first_word = query[tokens[0][0]:end].strip().lower()
    if first_word not in ("select", "with"):
        return "Queries must start with SELECT or WITH."
    return None


def run_sql(con, query):
    """Run a SELECT on `data`. Returns text; on any problem returns 'ERROR: ...'."""
    problem = check_sql(con, query)
    if problem:
        return f"ERROR: {problem}"

    # Timeout: a timer calls con.interrupt() if the query takes too long.
    timed_out = threading.Event()

    def stop_query():
        timed_out.set()
        con.interrupt()

    timer = threading.Timer(SQL_TIMEOUT_SECONDS, stop_query)
    timer.start()
    try:
        result = con.execute(query.strip().rstrip(";"))
        names = [d[0] for d in result.description]
        rows = result.fetchmany(MAX_ROWS + 1)
    except Exception as e:
        if timed_out.is_set():
            return f"ERROR: query took longer than {SQL_TIMEOUT_SECONDS} seconds and was stopped."
        return f"ERROR: {e}"
    finally:
        timer.cancel()

    text = format_rows(names, rows[:MAX_ROWS])
    if len(rows) > MAX_ROWS:
        text += f"\n(showing first {MAX_ROWS} rows only; aggregate or add LIMIT)"
    elif not rows:
        text += "\n(0 rows)"
    return text


# Tool definitions Claude sees. Names match guidelines.md.
TOOLS = [
    {
        "name": "describe_table",
        "description": "Show the columns, types, row count and 5 sample rows of the `data` table. Call this first.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql",
        "description": "Run ONE DuckDB SELECT (or WITH) query on the table `data`. Returns up to 50 rows, or 'ERROR: ...'.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A DuckDB SELECT query"}},
            "required": ["query"],
        },
    },
    {
        "name": "finish",
        "description": "Give the final answer to the user. Ends the run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "The final answer, in the format from the guidelines"},
                "sql_used": {"type": "string", "description": "The SQL query that produced the number(s) in the answer"},
            },
            "required": ["answer", "sql_used"],
        },
    },
]


# ---------------------------------------------------------------- the loop
def run_agent(con, question, on_step=None):
    """Answer one question about the data.

    Returns {"answer": str, "sql_used": str, "steps": list}.
    on_step(tool_name, tool_input, short_result) is called after every tool call.
    """
    client = anthropic.Anthropic(api_key=get_api_key())
    messages = [{"role": "user", "content": question}]
    steps = []
    last_sql = ""   # remembers the latest run_sql query, as a fallback for sql_used

    def record(name, tool_input, result):
        """Save a step and tell the UI about it."""
        short = result if len(result) <= SHORT_RESULT_CHARS else result[:SHORT_RESULT_CHARS] + "..."
        steps.append({"tool": name, "input": tool_input, "result": short})
        if on_step:
            on_step(name, tool_input, short)

    def finished(tool_input):
        """Build the return value from a finish call."""
        answer = tool_input.get("answer", "")
        sql_used = tool_input.get("sql_used") or last_sql
        record("finish", tool_input, answer)
        return {"answer": answer, "sql_used": sql_used, "steps": steps}

    client_kwargs = dict(model=MODEL, max_tokens=MAX_TOKENS, system=GUIDELINES, tools=TOOLS)

    for _ in range(MAX_STEPS):
        # 1. Ask Claude what to do next.
        response = client.messages.create(messages=messages, **client_kwargs)
        messages.append({"role": "assistant", "content": response.content})

        # 2. Find the tool calls in the reply.
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            messages.append({"role": "user", "content": "Please call a tool. Use finish for your final answer."})
            continue

        # 3. Run each tool call and collect the results.
        results = []
        for call in tool_calls:
            if call.name == "finish":
                return finished(call.input)
            if call.name == "describe_table":
                output = describe_table(con)
            elif call.name == "run_sql":
                last_sql = call.input.get("query", "")
                output = run_sql(con, last_sql)
            else:
                output = f"ERROR: unknown tool {call.name}"
            record(call.name, call.input, output)
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": output})

        # 4. Send the results back and loop again.
        messages.append({"role": "user", "content": results})

    # Step limit reached: force Claude to give its best answer now via finish.
    response = client.messages.create(
        messages=messages,
        tool_choice={"type": "tool", "name": "finish"},
        **client_kwargs,
    )
    call = next(b for b in response.content if b.type == "tool_use")
    return finished(call.input)
