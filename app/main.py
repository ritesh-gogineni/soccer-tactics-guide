# app/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from .prompts import BASE_SYSTEM_PROMPT, ARTICLE_TEMPLATES
from .llmclient import generate_article  # make sure filename is llmclient.py
from .rag import search_context


app = FastAPI(title="Soccer Article Generator")

# CORS middleware so the browser (index.html on another port) can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # allow all origins (fine for a local project)
    allow_credentials=True,
    allow_methods=["*"],        # allow GET, POST, OPTIONS, etc.
    allow_headers=["*"],        # allow any headers
)


class GenerateRequest(BaseModel):
    article_type: str  # "match_preview", "tactical_analysis", "player_profile"
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    team: Optional[str] = None
    player: Optional[str] = None
    competition: Optional[str] = None
    angle: Optional[str] = None
    tone: str = "Neutral"
    length: int = 800


class GenerateResponse(BaseModel):
    article: str


@app.get("/")
def read_root():
    return {"message": "Soccer Article Generator API is running."}


@app.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest):
    template = ARTICLE_TEMPLATES.get(payload.article_type)
    if not template:
        raise HTTPException(status_code=400, detail="Invalid article_type.")

    user_prompt = template.format(
        home_team=payload.home_team or "",
        away_team=payload.away_team or "",
        team=payload.team or "",
        player=payload.player or "",
        competition=payload.competition or "",
        angle=payload.angle or "",
        tone=payload.tone,
        length=payload.length,
    )

    query_parts = [
        payload.article_type,
        payload.home_team or "",
        payload.away_team or "",
        payload.team or "",
        payload.player or "",
        payload.competition or "",
        payload.angle or "",
    ]
    retrieval_query = " ".join(p for p in query_parts if p)

    chunks = search_context(retrieval_query, k=5) if retrieval_query else []
    context_text = "\n\n---\n\n".join(c["text"] for c in chunks) if chunks else ""

    article_text = generate_article(
        system_prompt=BASE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        context=context_text,
    )

    return GenerateResponse(article=article_text)
