"""
Tavily web search utility.
"""

import os
from typing import List

from schemas import EvidenceItem


def perform_tavily_search(query: str) -> List[EvidenceItem]:
    """Search Tavily for a query and return a list of EvidenceItem objects."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query=query, max_results=3)

    return [
        EvidenceItem(
            source=result.get("url", "Unknown"),
            title=result.get("title", "Untitled"),
            content=result.get("content", "")[:500],
        )
        for result in results.get("results", [])
    ]
