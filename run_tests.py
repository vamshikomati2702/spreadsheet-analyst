"""Run the 5 questions from tests.md through the agent and save a full trace.

Usage:  python run_tests.py           (needs ANTHROPIC_API_KEY in the environment)
Output: test_results.txt
"""

import agent

QUESTIONS = [
    "How many tickets are tagged Urgent even though the customer says it’s not urgent?",
    "Which ticket mentions the biggest file, and what plan is that customer on?",
    "Do Free customers have smaller teams than Enterprise customers?",
    "For tickets about broken imports or garbled characters, which tool did customers export from most often?",
    "What’s the average time to resolve a billing ticket?",
]

con = agent.load_csv("sample.csv")
with open("test_results.txt", "w", encoding="utf-8") as out:
    for i, q in enumerate(QUESTIONS, 1):
        print(f"Running {i}/5 ...")
        out.write(f"##### Q{i}: {q}\n")
        try:
            r = agent.run_agent(con, q)
            for n, s in enumerate(r["steps"], 1):
                out.write(f"step {n} [{s['tool']}] {s['input']}\n   -> {s['result']}\n")
            out.write(f"STEPS: {len(r['steps'])}\nANSWER:\n{r['answer']}\nSQL_USED: {r['sql_used']}\n\n")
        except Exception as e:
            out.write(f"FAILED TO RUN: {e}\n\n")
        out.flush()
print("Done. See test_results.txt")
