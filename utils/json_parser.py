"""
Utility for parsing JSON from LLM responses.
Handles responses wrapped in markdown code blocks and various formats.
"""

import json
import re


def parse_json_from_response(content: str) -> dict:
    """Extract and parse JSON from LLM response, handling markdown code blocks."""
    # Strategy 1: markdown code block
    if "```json" in content:
        block = content.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
    elif "```" in content:
        block = content.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # Strategy 2: direct parse
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 3: find first { ... } block via brace matching
    start = content.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i+1])
                    except json.JSONDecodeError:
                        break

    raise json.JSONDecodeError("No valid JSON found in response", content, 0)
