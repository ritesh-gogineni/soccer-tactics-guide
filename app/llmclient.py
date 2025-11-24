# app/llm_client.py

import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load variables from .env (including GEMINI_API_KEY)
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in .env")

# Configure the Gemini client
genai.configure(api_key=api_key)

# Choose a model. You can change this to another Gemini model if you like.
MODEL_NAME = "gemini-2.5-flash"


def generate_article(system_prompt: str, user_prompt: str) -> str:
    """
    Call the Google Gemini model and return the article text.
    We combine the system prompt and user prompt into a single prompt string.
    """
    model = genai.GenerativeModel(MODEL_NAME)

    # Combine system and user prompts into one big prompt
    full_prompt = system_prompt.strip() + "\n\n" + user_prompt.strip()

    response = model.generate_content(full_prompt)

    # response.text is a convenience property with the main text content
    if not hasattr(response, "text") or response.text is None:
        raise RuntimeError("No text returned from Gemini model")

    return response.text
