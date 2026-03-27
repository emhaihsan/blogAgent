"""
Graph builder: wires all nodes together into a compiled LangGraph.
"""

from langgraph.graph import StateGraph, START, END

from graph.state import BlogState
from nodes.router import router_node, route_after_router
from nodes.research import research_node
from nodes.orchestrator import orchestrator_node, fan_out_to_workers
from nodes.worker import worker_node
from nodes.reducer import reducer_node


def build_graph():
    """Build and compile the Blog Writing Agent graph (Stage 2)."""
    graph = StateGraph(BlogState)

    graph.add_node("router", router_node)
    graph.add_node("research_node", research_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("worker_node", worker_node)
    graph.add_node("reducer", reducer_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"research_node": "research_node", "orchestrator": "orchestrator"},
    )

    graph.add_edge("research_node", "orchestrator")
    graph.add_conditional_edges("orchestrator", fan_out_to_workers, ["worker_node"])
    graph.add_edge("worker_node", "reducer")
    graph.add_edge("reducer", END)

    return graph.compile()
