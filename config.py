"""
Configuration and shared LLM client initialization.
Import `model` from this module in any node that needs the LLM.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

model = ChatOpenAI(model="gpt-5-nano", temperature=0.7)

OUTPUT_DIR = "output"
