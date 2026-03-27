"""
Research Node: Generates search queries and fetches evidence via Tavily.
"""

from config import model
from graph.state import BlogState
from schemas import EvidencePack
from utils.json_parser import parse_json_from_response
from utils.search import perform_tavily_search

_SYSTEM_PROMPT = """You are a research assistant. Given a blog topic, generate 3-5 specific search
queries that would help gather comprehensive, up-to-date information for writing
a detailed blog post on this topic.

Make queries specific and diverse:
- Cover different angles of the topic
- Include queries for recent developments
- Include queries for key facts and statistics
- Avoid overly broad or vague queries

Return as JSON:
{
  "queries": ["query 1", "query 2", "query 3", ...]
}"""


def research_node(state: BlogState) -> dict:
    """Generate search queries and fetch evidence from the web via Tavily."""
    topic = state["topic"]

    # Step 1: Generate search queries
    response = model.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", f"Topic: {topic}")
    ])

    queries = parse_json_from_response(response.content).get("queries", [])
    print(f"[Research] Generated {len(queries)} search queries")

    # Step 2: Execute searches
    all_evidence = []
    for query in queries:
        print(f"[Research] Searching: {query}")
        try:
            items = perform_tavily_search(query)
            all_evidence.extend(items)
            print(f"[Research] Found {len(items)} results")
        except Exception as e:
            print(f"[Research] Error on '{query}': {e}")

    print(f"[Research] Total evidence: {len(all_evidence)} items")

    return {
        "search_queries": queries,
        "evidence": EvidencePack(items=all_evidence),
    }
