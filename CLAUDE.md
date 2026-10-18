# Spreadsheet Analyst - project rules

Claude Code is the developer here, NOT the runtime. The finished app must run
with only Python and an ANTHROPIC_API_KEY.

- Use the `anthropic` Python SDK Messages API with a hand-written tool-use loop.
- Do NOT use the Claude Agent SDK, LangChain, LlamaIndex, any agent framework,
  subagents, or MCP servers.
- Files: agent.py (loop + tools), app.py (Streamlit UI), cli.py (terminal
  testing), requirements.txt, README.md.
- API keys only from environment variables or st.secrets. Never hardcode.
- Keep code simple and commented for a beginner.
- guidelines.md is the agent's system prompt. Do not edit it.
