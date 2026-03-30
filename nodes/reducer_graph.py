"""
Reducer sub-graph nodes for Stage 3:
1. merge_content - Combine worker outputs
2. decide_images - Identify where images should go
3. generate_and_place_images - Generate images via Gemini and replace placeholders
"""

import os
import re

from config import model, OUTPUT_DIR
from graph.state import BlogState
from schemas import ImageSpec
from utils.json_parser import parse_json_from_response
from utils.image_generation import gemini_generate_image


def merge_content_node(state: BlogState) -> dict:
    """Combine all parallel worker outputs into a single markdown string."""
    title = state["plan"].title
    sections = state["completed_sections"]
    merged = f"# {title}\n\n" + "\n\n".join(sections)
    print(f"[Merge] Combined {len(sections)} sections into merged_markdown")
    return {"merged_markdown": merged}


_DECIDE_IMAGES_PROMPT = """You are an expert technical editor and visual content planner.

Given a complete blog post in markdown, your job is to:
1. Identify 1-3 locations where images would materially improve understanding
2. Insert placeholders at those locations using the format: ![description]({{IMAGE_1}})
3. For each placeholder, write a detailed image generation prompt

You MUST respond with valid JSON in this exact format:
{{
  "markdown_with_placeholders": "<the full blog markdown with placeholders inserted>",
  "images": [
    {{
      "placeholder": "{{{{IMAGE_1}}}}",
      "file_name": "descriptive_name.png",
      "prompt": "Detailed prompt describing the image to generate"
    }}
  ]
}}

Rules:
- Maximum 3 images per blog
- Only add images where they genuinely improve understanding
- Do NOT add decorative images
- If no images are needed, return the original markdown with an empty images list
- The markdown_with_placeholders MUST be a single string (not a list)
"""


def _normalize_image_data(raw: dict) -> tuple:
    """Extract markdown and image specs from raw LLM JSON, handling various formats."""
    # --- Extract markdown ---
    markdown = ""
    for key in ("markdown_with_placeholders", "content", "markdown", "blog"):
        val = raw.get(key)
        if isinstance(val, str) and len(val) > 50:
            markdown = val
            break
        elif isinstance(val, list):
            # LLM sometimes returns markdown as list of lines
            markdown = "\n".join(str(line) for line in val)
            break

    # --- Extract image specs ---
    specs = []
    raw_images = raw.get("images", [])
    if not isinstance(raw_images, list):
        raw_images = []

    for i, img in enumerate(raw_images):
        if not isinstance(img, dict):
            continue
        # Normalize placeholder
        placeholder = str(img.get("placeholder", img.get("id", f"IMAGE_{i+1}")))
        if not placeholder.startswith("{{"):
            placeholder = "{{" + placeholder.rstrip("}}").lstrip("{{") + "}}"
        if not re.match(r"\{\{IMAGE_\d+\}\}", placeholder):
            placeholder = f"{{{{IMAGE_{i+1}}}}}"
        # Normalize file_name
        file_name = str(img.get("file_name", img.get("filename", f"image_{i+1}.png")))
        if not file_name.endswith((".png", ".jpg", ".jpeg")):
            file_name = f"image_{i+1}.png"
        # Normalize prompt
        prompt = str(img.get("prompt", img.get("description", "")))
        if prompt:
            specs.append(ImageSpec(placeholder=placeholder, file_name=file_name, prompt=prompt))

    return markdown, specs


def decide_images_node(state: BlogState) -> dict:
    """Identify where images should go and create image generation plan."""
    merged = state["merged_markdown"]

    response = model.invoke([
        ("system", _DECIDE_IMAGES_PROMPT),
        ("human", f"Plan images for this blog and respond with valid JSON:\n\n{merged[:8000]}")
    ])

    # Parse the JSON from the response
    try:
        raw = parse_json_from_response(response.content)
        markdown, image_specs = _normalize_image_data(raw)
    except Exception as e:
        print(f"[DecideImages] JSON parsing failed: {e}")
        markdown = ""
        image_specs = []

    # Fallback: if parsing produced no/short markdown, use original
    if not markdown or len(markdown) < 100:
        print(f"[DecideImages] Using original merged markdown (LLM returned empty/short)")
        markdown = merged

    print(f"[DecideImages] {len(image_specs)} images planned, markdown={len(markdown)} chars")
    for spec in image_specs:
        print(f"  - {spec.placeholder}: {spec.file_name}")

    return {
        "markdown_with_placeholders": markdown,
        "image_specs": image_specs,
    }


def generate_and_place_images_node(state: BlogState) -> dict:
    """Generate images via Gemini and replace placeholders with actual image paths."""
    markdown = state["markdown_with_placeholders"]
    image_specs = state.get("image_specs", [])

    images_dir = os.path.join(OUTPUT_DIR, "images")
    os.makedirs(images_dir, exist_ok=True)

    for i, spec in enumerate(image_specs):
        file_name = spec.file_name
        file_path = os.path.join(images_dir, file_name)
        print(f"[GenerateImage] Creating {file_name}...")

        try:
            generated_path = gemini_generate_image(prompt=spec.prompt, file_path=file_path)
            if generated_path:
                markdown = markdown.replace(spec.placeholder, f"images/{file_name}")
                print(f"[GenerateImage] ✓ {file_name}")
            else:
                markdown = markdown.replace(spec.placeholder, "")
                print(f"[GenerateImage] ✗ {file_name} failed")
        except Exception as e:
            print(f"[GenerateImage] Error for {file_name}: {e}")
            markdown = markdown.replace(spec.placeholder, "")

    # Save final blog
    output_path = os.path.join(OUTPUT_DIR, "blog.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"[GenerateImage] Final blog saved ({len(markdown)} chars)")
    return {"final_blog": markdown}
