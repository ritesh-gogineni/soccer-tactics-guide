# app/prompts.py

BASE_SYSTEM_PROMPT = """
You are an expert football (soccer) writer for a tactics-focused website.
You write detailed, insightful, and original articles.
You never invent obviously wrong facts about final scores or transfers.
When facts are uncertain, you write in a cautious, speculative way.
Use clear headings and short paragraphs.
Use the latest news and tactical trends to inform your writing.
For match previews, use the next fixture date.
"""

ARTICLE_TEMPLATES = {
    "match_preview": """
Write a match preview article.

Teams: {home_team} vs {away_team}
Competition: {competition}
Tone: {tone}
Target length: {length} words.

Structure:
- Engaging intro setting the context
- Recent form & key storylines
- Tactical matchup (formations, pressing, build-up, weaknesses)
- Key players to watch
- What to expect (tempo, likely patterns)
- Closing paragraph with a cautious prediction

Write as if for an online tactics blog.
""",
    "tactical_analysis": """
Write a tactical analysis article.

Focus team: {team}
Specific angle: {angle}
Tone: {tone}
Target length: {length} words.

Include:
- Short context (coach, recent results)
- Base formation & typical shape in possession and out of possession
- Build-up patterns and pressing triggers
- Strengths and weaknesses
- How opponents try to disrupt them
- Summary of how this tactical approach might evolve

Use subheadings and detailed tactical language.
""",
    "player_profile": """
Write a player profile article.

Player: {player}
Team: {team}
Tone: {tone}
Target length: {length} words.

Include:
- Brief biography & career trajectory
- Playing style & tactical role
- Strengths and weaknesses
- Fit within current team’s tactics
- Future potential and ideal tactical environment

Write analytically but accessible to casual fans.
"""
}
