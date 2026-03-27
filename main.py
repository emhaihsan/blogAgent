"""
CLI entry point for the AI Blog Writing Agent.

Usage:
    python main.py "Your blog topic here"
    python main.py "Self Attention in Transformer Architecture"
    python main.py "Top AI News This Week"
"""

import sys
from graph.builder import build_graph

app = build_graph()


def run(topic: str) -> str:
    """Run the blog agent for a given topic and return the final blog markdown."""
    print(f"\n{'='*60}")
    print(f"Generating blog for: {topic}")
    print(f"{'='*60}\n")

    result = app.invoke({"topic": topic})

    print(f"\n{'='*60}")
    print(f"Done! Blog saved to output/blog.md")
    print(f"Total characters: {len(result['final_blog'])}")
    print(f"{'='*60}\n")

    return result["final_blog"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<topic>\"")
        sys.exit(1)

    topic = " ".join(sys.argv[1:])
    run(topic)
