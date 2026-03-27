"""
LangGraph state definitions for the Blog Writing Agent.
"""

import operator
from typing import TypedDict, List, Annotated

from schemas import Task, Plan, EvidencePack


class BlogState(TypedDict):
    """Shared state across all nodes in the main graph."""
    topic: str
    needs_research: bool
    search_queries: List[str]
    evidence: EvidencePack
    plan: Plan
    completed_sections: Annotated[List[str], operator.add]
    final_blog: str


class WorkerState(TypedDict):
    """State passed to each individual parallel worker node."""
    task: Task
    topic: str
    plan_title: str
    evidence: EvidencePack
