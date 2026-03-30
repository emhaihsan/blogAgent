"""
Pydantic schemas for the AI Blog Writing Agent.
Defines structured output models for LLM responses.
"""

from pydantic import BaseModel, Field
from typing import List


# =============================================================================
# Stage 1: Basic Blog Writing
# =============================================================================

class Task(BaseModel):
    """Represents one section/task of the blog."""
    id: str = Field(description="Unique identifier for the task, e.g. 'section_1'")
    title: str = Field(description="Title of this blog section")
    description: str = Field(description="Detailed description of what this section should cover")


class Plan(BaseModel):
    """The overall blog plan created by the orchestrator."""
    title: str = Field(description="The title of the blog")
    tasks: List[Task] = Field(description="Ordered list of section tasks for the blog")


# =============================================================================
# Stage 2: Research Capability
# =============================================================================

class RouterDecision(BaseModel):
    """Router's decision on whether internet research is needed."""
    needs_research: bool = Field(
        description="True if the topic requires internet research for recent/current information, False otherwise"
    )


class SearchQueries(BaseModel):
    """List of search queries to research the topic."""
    queries: List[str] = Field(
        description="List of specific search queries to perform on the internet"
    )


class EvidenceItem(BaseModel):
    """A single piece of evidence from research."""
    source: str = Field(description="URL or source name")
    title: str = Field(description="Title of the source")
    content: str = Field(description="Relevant content/snippet from the source")


class EvidencePack(BaseModel):
    """Collection of all research evidence."""
    items: List[EvidenceItem] = Field(default_factory=list)


# =============================================================================
# Stage 3: Image Generation (simple dataclasses, parsing done in node)
# =============================================================================

class ImageSpec(BaseModel):
    """Specification for one image to be generated."""
    placeholder: str = Field(description="Placeholder like '{{IMAGE_1}}'")
    file_name: str = Field(description="Target file name, e.g. 'diagram.png'")
    prompt: str = Field(description="Detailed image generation prompt")
