"""
Worker Node: Writes one blog section in parallel.
"""

from config import model
from graph.state import WorkerState
from schemas import EvidencePack

_SYSTEM_PROMPT_TEMPLATE = """You are an expert blog writer writing one section of a larger blog post.

Blog title: {plan_title}
Topic: {topic}
{evidence_text}

Your task:
- Section title: {section_title}
- What to cover: {section_description}

Rules:
1. Write ONLY this section
2. Use markdown formatting (## heading, ### sub-headings)
3. Clear, engaging, informative tone
4. Include code blocks with syntax highlighting where relevant
5. Do NOT include the blog title
6. If evidence is provided and relevant, cite sources as markdown links
"""


def _build_evidence_text(evidence: EvidencePack) -> str:
    if not evidence or not evidence.items:
        return ""
    lines = ["\n\nAvailable research evidence for citations:\n"]
    for i, item in enumerate(evidence.items[:5], 1):
        lines.append(f"[{i}] {item.title} - {item.source}\n{item.content[:300]}...\n")
    lines.append("\nCite sources using markdown links: [text](url) or [1], [2], etc.")
    return "\n".join(lines)


def worker_node(state: WorkerState) -> dict:
    """Write a single blog section based on the assigned task."""
    task = state["task"]
    evidence = state["evidence"]

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        plan_title=state["plan_title"],
        topic=state["topic"],
        evidence_text=_build_evidence_text(evidence),
        section_title=task.title,
        section_description=task.description,
    )

    response = model.invoke([
        ("system", system_prompt),
        ("human", f"Write the section '{task.title}'.")
    ])

    content = response.content
    print(f"[Worker] '{task.title}' -> {len(content)} chars")

    return {"completed_sections": [content]}
