"""
Backward-compatibility shim.
All logic has been moved to the modular package structure:
  config.py, graph/, nodes/, utils/

Import from the new modules directly for new code.
"""

from graph.builder import build_graph
from nodes.router import router_node, route_after_router
from nodes.research import research_node
from nodes.orchestrator import orchestrator_node, fan_out_to_workers
from nodes.worker import worker_node
from nodes.reducer import reducer_node
from graph.state import BlogState, WorkerState
from utils.json_parser import parse_json_from_response
from utils.search import perform_tavily_search

app = build_graph()

__all__ = [
    "app",
    "build_graph",
    "router_node",
    "route_after_router",
    "research_node",
    "orchestrator_node",
    "fan_out_to_workers",
    "worker_node",
    "reducer_node",
    "BlogState",
    "WorkerState",
    "parse_json_from_response",
    "perform_tavily_search",
]
