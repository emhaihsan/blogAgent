"""
Router Node: Decides if the topic requires internet research.
"""

from config import model
from graph.state import BlogState
from utils.json_parser import parse_json_from_response

_SYSTEM_PROMPT = """You are a research advisor. Given a blog topic, decide whether writing this blog
requires searching the internet for recent or current information.

Return your decision as a JSON object:
{
  "needs_research": true or false
}

Return needs_research = true if:
- The topic involves recent events, news, or developments (e.g., "Top AI News of January 2026")
- The topic references specific dates, statistics, or rapidly changing fields
- The topic requires up-to-date information that an LLM may not have

Return needs_research = false if:
- The topic is a well-established concept (e.g., "Self Attention", "Binary Search")
- The topic is educational/evergreen and does not depend on current events
- The LLM's existing knowledge is sufficient to write a comprehensive blog

Examples:
- "The Future of AI in 2030" -> true
- "Machine Learning Basics" -> false
- "State of Multimodal LLMs in 2026" -> true
- "How Transformers Work" -> false
"""


def router_node(state: BlogState) -> dict:
    """Decide if the topic needs internet research."""
    topic = state["topic"]

    response = model.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", f"Topic: {topic}")
    ])

    decision_data = parse_json_from_response(response.content)
    needs_research = decision_data.get("needs_research", False)

    print(f"[Router] '{topic}' -> needs_research={needs_research}")

    return {"needs_research": needs_research}


def route_after_router(state: BlogState) -> str:
    """Conditional edge: send to research_node or skip directly to orchestrator."""
    return "research_node" if state.get("needs_research", False) else "orchestrator"
