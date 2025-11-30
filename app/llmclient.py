import os
from typing import Optional

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


def generate_article(
    system_prompt: str,
    user_prompt: str,
    context: Optional[str] = None,
) -> str:
    """
    Call the Google Gemini model and return the article text.
    We combine the system prompt, optional retrieved context, and user prompt
    into a single prompt string.
    """
    model = genai.GenerativeModel(MODEL_NAME)

    parts = [system_prompt.strip()]
    if context:
        parts.append(
            "Here is background tactical context drawn from thefalse9.com. "
            "Use it to inspire your analysis and style, but do not copy any "
            "sentences verbatim:\n\n" + context.strip()
        )
    parts.append(user_prompt.strip())

    full_prompt = "\n\n".join(parts)

    response = model.generate_content(full_prompt)

    # response.text is a convenience property with the main text content
    if not hasattr(response, "text") or response.text is None:
        raise RuntimeError("No text returned from Gemini model")

    return response.text
