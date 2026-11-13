"""One configured model provider for both workflows and the combined agent."""
import os
from langchain_groq import ChatGroq


def get_model():
    return ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                    timeout=30, max_retries=1)
