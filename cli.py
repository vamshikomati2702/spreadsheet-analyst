"""Terminal tester.  Usage:
    python cli.py sample.csv "How many urgent tickets are there?"
"""

import sys

import agent


def show_step(tool_name, tool_input, short_result):
    """Print each tool call and a short preview of its result."""
    print(f"\n[{tool_name}] {tool_input or ''}")
    print("  ->", short_result.replace("\n", "\n     "))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    con = agent.load_csv(sys.argv[1])
    result = agent.run_agent(con, " ".join(sys.argv[2:]), on_step=show_step)
    print("\n=== ANSWER ===")
    print(result["answer"])
    print("\nSQL used:", result["sql_used"])


if __name__ == "__main__":
    main()
