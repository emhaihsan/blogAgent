"""
Utility for parsing JSON from LLM responses.
Handles responses wrapped in markdown code blocks.
"""

import json


def parse_json_from_response(content: str) -> dict:
    """Extract and parse JSON from LLM response, handling markdown code blocks."""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)
