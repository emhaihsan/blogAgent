"""
Backend module for the AI Blog Writing Agent.
Exports the compiled graph, run_agent helper, and all node/schema references.
"""

import os
import json
from datetime import datetime

from graph.builder import build_graph
from nodes.router import router_node, route_after_router
from nodes.research import research_node
from nodes.orchestrator import orchestrator_node, fan_out_to_workers
from nodes.worker import worker_node
from nodes.reducer import reducer_node
from nodes.reducer_graph import (
    merge_content_node,
    decide_images_node,
    generate_and_place_images_node,
)
from graph.state import BlogState, WorkerState
from utils.json_parser import parse_json_from_response
from utils.search import perform_tavily_search
from utils.image_generation import gemini_generate_image
from schemas import ImageSpec
from config import OUTPUT_DIR

app = build_graph()

HISTORY_DIR = "history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "blogs.json")

# Node display names in execution order
NODE_LABELS = {
    "router": "🔀 Router — Analyzing topic",
    "research_node": "🔍 Research — Searching the web",
    "orchestrator": "📋 Orchestrator — Creating plan",
    "worker_node": "✍️ Workers — Writing sections",
    "merge_content": "📑 Merge — Combining sections",
    "decide_images": "🖼️ Decide Images — Planning visuals",
    "generate_and_place_images": "🎨 Generate Images — Creating visuals",
}


def run_agent_stream(topic: str, instructions: str = ""):
    """Stream the blog agent execution, yielding (node_name, node_output) tuples.

    Yields partial results as each node completes. The final yield contains
    the complete state with all fields populated.
    """
    input_state = {"topic": topic}
    if instructions:
        input_state["topic"] = f"{topic}\n\nAdditional instructions: {instructions}"

    for event in app.stream(input_state):
        for node_name, node_output in event.items():
            yield node_name, node_output


def run_agent(topic: str, instructions: str = ""):
    """Run the blog agent and return structured results dict."""
    input_state = {"topic": topic}
    if instructions:
        input_state["topic"] = f"{topic}\n\nAdditional instructions: {instructions}"

    result = app.invoke(input_state)
    return result


def save_to_history(topic: str, result: dict) -> dict:
    """Save a blog generation result to history. Returns the history entry."""
    os.makedirs(HISTORY_DIR, exist_ok=True)

    history = load_history()

    plan = result.get("plan")
    image_specs = result.get("image_specs", [])

    entry = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "title": plan.title if plan else topic,
        "needs_research": result.get("needs_research", False),
        "num_sections": len(plan.tasks) if plan else 0,
        "num_images": len(image_specs),
        "blog_length": len(result.get("final_blog", "")),
        "plan": plan.model_dump() if plan else None,
        "evidence": result["evidence"].model_dump() if result.get("evidence") else None,
        "image_specs": [s.model_dump() for s in image_specs],
        "final_blog": result.get("final_blog", ""),
    }

    history.insert(0, entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return entry


def load_history() -> list:
    """Load blog history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def delete_history_entry(entry_id: str) -> bool:
    """Delete a history entry by its id."""
    history = load_history()
    history = [e for e in history if e.get("id") != entry_id]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    return True


__all__ = [
    "app",
    "build_graph",
    "run_agent",
    "run_agent_stream",
    "save_to_history",
    "load_history",
    "delete_history_entry",
    "NODE_LABELS",
    "HISTORY_DIR",
    "OUTPUT_DIR",
    "router_node",
    "route_after_router",
    "research_node",
    "orchestrator_node",
    "fan_out_to_workers",
    "worker_node",
    "reducer_node",
    "merge_content_node",
    "decide_images_node",
    "generate_and_place_images_node",
    "BlogState",
    "WorkerState",
    "parse_json_from_response",
    "perform_tavily_search",
    "gemini_generate_image",
    "ImageSpec",
]
