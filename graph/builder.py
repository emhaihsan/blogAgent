"""
Graph builder: wires all nodes together into a compiled LangGraph.
"""

from langgraph.graph import StateGraph, START, END

from graph.state import BlogState
from nodes.router import router_node, route_after_router
from nodes.research import research_node
from nodes.orchestrator import orchestrator_node, fan_out_to_workers
from nodes.worker import worker_node
from nodes.reducer_graph import (
    merge_content_node,
    decide_images_node,
    generate_and_place_images_node,
)


def build_graph():
    """Build and compile the Blog Writing Agent graph (Stage 3 with images)."""
    graph = StateGraph(BlogState)

    graph.add_node("router", router_node)
    graph.add_node("research_node", research_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("worker_node", worker_node)

    # Stage 3: Reducer sub-graph as 3 sequential nodes
    graph.add_node("merge_content", merge_content_node)
    graph.add_node("decide_images", decide_images_node)
    graph.add_node("generate_and_place_images", generate_and_place_images_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"research_node": "research_node", "orchestrator": "orchestrator"},
    )

    graph.add_edge("research_node", "orchestrator")
    graph.add_conditional_edges("orchestrator", fan_out_to_workers, ["worker_node"])

    # Reducer sub-graph edges
    graph.add_edge("worker_node", "merge_content")
    graph.add_edge("merge_content", "decide_images")
    graph.add_edge("decide_images", "generate_and_place_images")
    graph.add_edge("generate_and_place_images", END)

    return graph.compile()
