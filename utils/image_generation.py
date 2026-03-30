"""
Image generation utility using Google Gemini.
Uses gemini-2.5-flash-image for fast, efficient image generation.
"""

import os

from config import OUTPUT_DIR


def gemini_generate_image(prompt: str, file_path: str) -> str:
    """Generate an image using Gemini 2.5 Flash Image and save to file_path. Returns the file_path."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=['IMAGE'],
            image_config=types.ImageConfig(
                aspect_ratio="16:9",
            ),
        ),
    )

    # Save the image from inline_data
    for part in response.parts:
        if part.inline_data is not None:
            image = part.as_image()
            image.save(file_path)
            return file_path

    return ""
