"""
Backend implementation for AI Blog Writing Agent - Stage 2.
Adds research capability: Router -> Research (optional) -> Orchestrator -> Workers -> Reducer
"""

import os
import json
from typing import TypedDict, List, Annotated
import operator
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_openai import ChatOpenAI

from schemas import Task, Plan, RouterDecision, SearchQueries, EvidenceItem, EvidencePack

# Load environment variables
load_dotenv()

# Initialize LLM
model = ChatOpenAI(model="gpt-5-nano", temperature=0.7)


# =============================================================================
# Graph State
# =============================================================================

class BlogState(TypedDict):
    """State shared across all nodes in the graph."""
    topic: str                          # user-provided topic
    needs_research: bool                # NEW: from router
    search_queries: List[str]           # NEW: from research node
    evidence: EvidencePack             # NEW: research results
    plan: Plan                          # orchestrator output
    completed_sections: Annotated[List[str], operator.add]  # worker outputs (reducer merges these)
    final_blog: str                     # final combined markdown


class WorkerState(TypedDict):
    """State passed to each individual worker node."""
    task: Task
    topic: str
    plan_title: str
    evidence: EvidencePack             # NEW: for citations


# =============================================================================
# Helper Functions
# =============================================================================

def parse_json_from_response(content: str) -> dict:
    """Extract and parse JSON from LLM response, handling markdown code blocks."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def perform_tavily_search(query: str) -> List[EvidenceItem]:
    """Search Tavily for a query and return evidence items."""
    from tavily import TavilyClient
    
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query=query, max_results=3)
    
    evidence_items = []
    for result in results.get("results", []):
        evidence_items.append(EvidenceItem(
            source=result.get("url", "Unknown"),
            title=result.get("title", "Untitled"),
            content=result.get("content", "")[:500]  # Limit content length
        ))
    
    return evidence_items

def router_node(state: BlogState) -> dict:
    """
    Router Node: Decides if the topic needs internet research.
    Input: topic
    Output: needs_research boolean
    """
    topic = state["topic"]
    
    system_prompt = """You are a research advisor. Given a blog topic, decide whether writing this blog
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
    
    response = model.invoke([
        ("system", system_prompt),
        ("human", f"Topic: {topic}")
    ])
    
    decision_data = parse_json_from_response(response.content)
    needs_research = decision_data.get("needs_research", False)
    
    print(f"[Router] Topic: '{topic}' -> Needs research: {needs_research}")
    
    return {"needs_research": needs_research}


def route_after_router(state: BlogState) -> str:
    """Conditional edge: route to research or directly to orchestrator."""
    if state.get("needs_research", False):
        return "research_node"
    else:
        return "orchestrator"


def research_node(state: BlogState) -> dict:
    """
    Research Node: Generates search queries and fetches evidence via Tavily.
    Input: topic
    Output: search_queries and evidence
    """
    topic = state["topic"]
    
    # Step 1: Generate search queries
    system_prompt = """You are a research assistant. Given a blog topic, generate 3-5 specific search
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
    
    response = model.invoke([
        ("system", system_prompt),
        ("human", f"Topic: {topic}")
    ])
    
    queries_data = parse_json_from_response(response.content)
    queries = queries_data.get("queries", [])
    
    print(f"[Research] Generated {len(queries)} search queries")
    
    # Step 2: Execute searches via Tavily
    all_evidence = []
    for query in queries:
        print(f"[Research] Searching: {query}")
        try:
            evidence_items = perform_tavily_search(query)
            all_evidence.extend(evidence_items)
            print(f"[Research] Found {len(evidence_items)} results")
        except Exception as e:
            print(f"[Research] Error searching '{query}': {e}")
    
    evidence_pack = EvidencePack(items=all_evidence)
    
    print(f"[Research] Total evidence collected: {len(all_evidence)} items")
    
    return {
        "search_queries": queries,
        "evidence": evidence_pack
    }


def orchestrator_node(state: BlogState) -> dict:
    """
    Orchestrator Node: Creates a structured plan for the blog.
    Input: topic + optional evidence
    Output: plan (title + list of tasks/sections)
    """
    topic = state["topic"]
    evidence = state.get("evidence", EvidencePack())
    needs_research = state.get("needs_research", False)
    
    # Build evidence context
    evidence_text = "No research evidence available."
    if needs_research and evidence.items:
        evidence_text = "Research Evidence:\n\n"
        for i, item in enumerate(evidence.items[:10], 1):  # Limit to 10 items
            evidence_text += f"{i}. {item.title}\n   Source: {item.source}\n   Content: {item.content[:200]}...\n\n"
    
    system_prompt = f"""You are an expert blog planner. Given a topic and optional research evidence,
create a detailed plan for a comprehensive blog post.

Topic: {{topic}}

{{evidence}}

Your plan must include:
1. A compelling blog title
2. A list of sections (tasks), each with:
   - A unique id (e.g., "section_1", "section_2", ...)
   - A clear section title
   - A detailed description of what the section should cover
   - Indicate whether this section should cite sources from the evidence (if available)
   - Indicate whether this section needs code examples
   - Target word count (150-400 words per section)

Guidelines:
- Create 5-8 sections for a thorough blog
- If research evidence is provided, incorporate relevant findings into section descriptions
- Indicate which sections should cite sources
- Ensure logical flow between sections
- Start with an introduction and end with a conclusion

IMPORTANT: Return your response as a valid JSON object with this exact structure:
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
    
    # Format prompt with evidence
    formatted_prompt = system_prompt.format(topic=topic, evidence=evidence_text)
    
    response = model.invoke([
        ("system", formatted_prompt),
        ("human", f"Create a blog plan for: {topic}")
    ])
    
    plan_data = parse_json_from_response(response.content)
    plan = Plan(**plan_data)
    
    print(f"[Orchestrator] Created plan with title: {plan.title}")
    print(f"[Orchestrator] Number of sections: {len(plan.tasks)}")
    
    return {"plan": plan}


def fan_out_to_workers(state: BlogState) -> List[Send]:
    """
    Fan-out Logic: Creates one Send() per task in the plan.
    This enables parallel execution of worker nodes.
    """
    plan = state["plan"]
    evidence = state.get("evidence", EvidencePack())
    
    sends = [
        Send("worker_node", {
            "task": task,
            "topic": state["topic"],
            "plan_title": plan.title,
            "evidence": evidence
        })
        for task in plan.tasks
    ]
    
    print(f"[Fan-out] Spawning {len(sends)} worker nodes")
    return sends


def worker_node(state: WorkerState) -> dict:
    """
    Worker Node: Writes one blog section.
    Input: task, topic, plan_title, evidence
    Output: completed section text (markdown with citations if evidence available)
    """
    task = state["task"]
    topic = state["topic"]
    plan_title = state["plan_title"]
    evidence = state["evidence"]
    
    # Build evidence context for citations
    evidence_text = ""
    if evidence and evidence.items:
        evidence_text = "\n\nAvailable research evidence for citations:\n\n"
        for i, item in enumerate(evidence.items[:5], 1):
            evidence_text += f"[{i}] {item.title} - {item.source}\n{item.content[:300]}...\n\n"
        evidence_text += "\nIf relevant, cite sources using markdown links: [text](url) or [1], [2], etc."
    
    system_prompt = f"""You are an expert blog writer. You are writing one section of a larger blog post.

Blog title: {plan_title}
Topic: {topic}
{evidence_text}

Your task:
- Section title: {task.title}
- What to cover: {task.description}

Rules:
1. Write ONLY this section - do not write an introduction or conclusion unless
   that is specifically your assigned section
2. Use markdown formatting (## for section heading, ### for sub-headings)
3. Write in a clear, engaging, and informative tone
4. Include code blocks with syntax highlighting where relevant
5. Target the word count suggested in the description
6. Do NOT include the blog title - only your section content
7. If evidence is provided and relevant, cite sources using markdown links
"""
    
    response = model.invoke([
        ("system", system_prompt),
        ("human", f"Write the section '{task.title}' for the blog.")
    ])
    
    section_content = response.content
    print(f"[Worker] Completed section: {task.title} ({len(section_content)} chars)")
    
    return {"completed_sections": [section_content]}


def reducer_node(state: BlogState) -> dict:
    """
    Reducer Node: Merges all completed sections into final blog.
    Input: plan.title, completed_sections list
    Output: final_blog (markdown string)
    """
    title = state["plan"].title
    sections = state["completed_sections"]
    
    # Merge sections
    merged = f"# {title}\n\n" + "\n\n".join(sections)
    
    # Ensure output directory exists
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to file
    output_path = os.path.join(output_dir, "blog.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(merged)
    
    print(f"[Reducer] Merged {len(sections)} sections into final blog")
    print(f"[Reducer] Saved to: {output_path}")
    
    return {"final_blog": merged}


# =============================================================================
# Build and Compile Graph
# =============================================================================

def build_graph():
    """Build and compile the LangGraph for Stage 2 (with research capability)."""
    
    # Create graph with BlogState
    graph = StateGraph(BlogState)
    
    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("research_node", research_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("worker_node", worker_node)
    graph.add_node("reducer", reducer_node)
    
    # Add edges
    graph.add_edge(START, "router")
    
    # Conditional edge: router decides research or direct to orchestrator
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "research_node": "research_node",
            "orchestrator": "orchestrator"
        }
    )
    
    # Research feeds into orchestrator
    graph.add_edge("research_node", "orchestrator")
    
    # Orchestrator fans out to workers
    graph.add_conditional_edges("orchestrator", fan_out_to_workers, ["worker_node"])
    
    # Workers feed into reducer
    graph.add_edge("worker_node", "reducer")
    graph.add_edge("reducer", END)
    
    # Compile
    return graph.compile()


# Create compiled app instance
app = build_graph()
