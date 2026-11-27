"""
Kept so existing imports keep working. The IT prompt lives with the IT agent
(app/careers/agents/it/prompt.py); the text is unchanged.
"""
from app.careers.agents.it.prompt import IT_SYSTEM_PROMPT as COACH_SYSTEM_PROMPT

__all__ = ["COACH_SYSTEM_PROMPT"]
