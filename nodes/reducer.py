"""
Reducer Node: Merges all completed sections into the final blog and saves to disk.
"""

import os

from config import OUTPUT_DIR
from graph.state import BlogState


def reducer_node(state: BlogState) -> dict:
    """Merge all completed sections into a single markdown blog and save to disk."""
    title = state["plan"].title
    sections = state["completed_sections"]

    final_blog = f"# {title}\n\n" + "\n\n".join(sections)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "blog.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_blog)

    print(f"[Reducer] Merged {len(sections)} sections -> {output_path}")

    return {"final_blog": final_blog}
