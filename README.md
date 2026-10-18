# Spreadsheet Analyst

Upload a CSV (or try the included `sample.csv`) and ask questions about it in
plain English. An AI agent (Claude) looks at the table, writes DuckDB SQL,
runs it, checks the results, and gives a short answer. The SQL behind every
answer is shown so you can check it yourself.

## Limits (please read)

- **Privacy:** your file's contents are sent to an AI model (Anthropic's API)
  for analysis. The app doesn't store files, but don't upload sensitive data.
- **One CSV at a time, max 10 MB.** Questions are independent; the agent does
  not remember earlier ones.
- **5 questions per browser session**, 300 characters each. The counter resets
  if the page is refreshed, so it slows casual use but is not strong abuse
  protection.
- **Max 8 agent steps** per question, and each SQL query is stopped after 10 s.
- **Read-only:** only a single `SELECT`/`WITH` on the table `data` is allowed;
  file and network access are switched off. See `test_security.py`.
- **Answers can be wrong.** The agent can misread messy text columns. Check
  the queries in "Queries used" before relying on a number. Answers about
  free-text columns depend on the patterns the agent picks.
- **Memory:** a hostile query can still allocate a lot of memory (DuckDB
  doesn't count giant strings/lists against its limit). Community Cloud has
  its own memory cap; for other hosts use a container memory limit.
- Needs an Anthropic API key; every question costs a small amount of API credit.

## Run locally

```bash
pip install -r requirements.txt
```

Put your key in `.streamlit/secrets.toml` (this file is gitignored):

```toml
ANTHROPIC_API_KEY = "your-key"
```

Then:

```bash
python -m streamlit run app.py
```

(`python -m` avoids the "streamlit is not recognized" error on Windows.)
Terminal version: `python cli.py sample.csv "How many tickets per plan?"`

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub. Check `.streamlit/secrets.toml` is NOT in it.
2. On share.streamlit.io choose **Create app**, pick the repo, branch and
   `app.py` as the main file.
3. Open **Advanced settings -> Secrets** and paste:
   ```toml
   ANTHROPIC_API_KEY = "your-key"
   ```
4. Deploy. The upload limit comes from `.streamlit/config.toml` (10 MB).
5. Set a monthly spend limit on the key in the Anthropic Console, since
   anyone with the link can use it (5 questions per session each).

## Files

- `agent.py` - the tool-use loop and tools (`describe_table`, `run_sql`, `finish`)
- `app.py` - Streamlit UI
- `cli.py` - terminal tester
- `guidelines.md` - the agent's system prompt
- `sample.csv` - demo support-ticket data
- `tests.md`, `run_tests.py` - 5 hand-checked questions and a script that runs them
- `test_security.py` - tries to break the SQL guard

## How the agent works

1. Your question goes to Claude along with the tool list and `guidelines.md`.
2. Claude calls `describe_table`, then `run_sql` as many times as needed.
3. Each result (or error) goes back to Claude so it can fix its query.
4. Claude calls `finish` with the answer.

Change the model with `MODEL` in `agent.py`.
