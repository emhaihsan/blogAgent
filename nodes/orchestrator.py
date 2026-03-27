"""
Orchestrator Node: Creates a structured blog plan.
Fan-out function: spawns parallel workers from the plan.
"""

from typing import List

from langgraph.types import Send

from config import model
from graph.state import BlogState
from schemas import Plan, EvidencePack
from utils.json_parser import parse_json_from_response

_SYSTEM_PROMPT_TEMPLATE = """You are an expert blog planner. Given a topic and optional research evidence,
create a detailed plan for a comprehensive blog post.

Topic: {topic}

{evidence_text}

Your plan must include:
1. A compelling blog title
2. A list of sections (tasks), each with:
   - A unique id (e.g., "section_1", "section_2", ...)
   - A clear section title
   - A detailed description of what the section should cover
   - Whether this section should cite sources (if evidence is available)
   - Whether this section needs code examples
   - Target word count (150-400 words per section)

Guidelines:
- Create 5-8 sections for a thorough blog
- If research evidence is provided, incorporate relevant findings
- Ensure logical flow: start with an introduction, end with a conclusion

IMPORTANT: Return a valid JSON object with this exact structure:
{{
  "title": "Blog Title Here",
  "tasks": [
    {{
      "id": "section_1",
      "title": "Section Title",
      "description": "Detailed description..."
    }},
    ...
  ]
}}
"""


def _build_evidence_text(evidence: EvidencePack, needs_research: bool) -> str:
    if not needs_research or not evidence.items:
        return "No research evidence available."
    lines = ["Research Evidence:\n"]
    for i, item in enumerate(evidence.items[:10], 1):
        lines.append(
            f"{i}. {item.title}\n   Source: {item.source}\n   Content: {item.content[:200]}...\n"
        )
    return "\n".join(lines)


def orchestrator_node(state: BlogState) -> dict:
    """Create a structured plan for the blog, optionally informed by research evidence."""
    topic = state["topic"]
    evidence = state.get("evidence", EvidencePack())
    needs_research = state.get("needs_research", False)

    evidence_text = _build_evidence_text(evidence, needs_research)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(topic=topic, evidence_text=evidence_text)

    response = model.invoke([
        ("system", system_prompt),
        ("human", f"Create a blog plan for: {topic}")
    ])

    plan = Plan(**parse_json_from_response(response.content))

    print(f"[Orchestrator] Plan: '{plan.title}' ({len(plan.tasks)} sections)")

    return {"plan": plan}


def fan_out_to_workers(state: BlogState) -> List[Send]:
    """Spawn one parallel worker per section in the plan."""
    plan = state["plan"]
    evidence = state.get("evidence", EvidencePack())

    sends = [
        Send("worker_node", {
            "task": task,
            "topic": state["topic"],
            "plan_title": plan.title,
            "evidence": evidence,
        })
        for task in plan.tasks
    ]

    print(f"[Fan-out] Spawning {len(sends)} workers")
    return sends
