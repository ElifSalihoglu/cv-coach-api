"""
How the General agent hands a posting to specialists. The model, acting as the General agent, is shown
one tool per registered specialist, built from that specialist's card, and either calls one or calls
none (it is done, or it answers itself). After a specialist ran, a short summary of its result comes
back as the tool message and the model may call another specialist or stop. It sees the posting and
the target position only, never the CV.

Nothing here names a domain: a new specialist registered in `assembly.py` shows up as a new tool with
no change to this module, the General agent or the orchestrator. A tool name the model invents or
repeats is ignored, as if it had called none.
"""

import json
import logging
from typing import Sequence

from app.careers.core.state import AgentCard, CareerCase
from app.logging_utils import log_event
from app.models.coaching import CoachResult
from app.services.llm_client import ContentGenerator, ToolSpec, ToolStep

logger = logging.getLogger("app.delegation")

TOOL_PREFIX = "ask_"

DELEGATION_PROMPT = """You are the General career agent. You receive a job posting and decide who analyses it.
Specialist agents are available as tools. If the posting clearly belongs to one specialist's field, call that
specialist's tool. If it does not clearly belong to any of them, or you are unsure, call no tool: you will
analyse the posting yourself. Judge the profession of the posting (its title and main duties), not the
wording of any single keyword: a duty that only touches another field (supporting pupils with special needs,
first aid, payroll forms, using software) does not make the posting belong to that field. A profession that no
specialist tool describes, such as teaching, retail, hospitality, trades or administration, has no specialist:
call no tool.
A posting can span two fields (for example an AI engineer role in a hospital). Then call the specialist of
the main field first. When its result comes back, call a second specialist only if the posting clearly
needs that other field's expertise too; otherwise call no tool. Call one tool at a time, and never the
same specialist twice. Calling no tool after a result means you are finished."""


def tool_name(card: AgentCard) -> str:
    return TOOL_PREFIX + card.id


def specialist_tools(cards: list[AgentCard]) -> list[ToolSpec]:
    tools = []
    for card in cards:
        text = f"Hand this posting to the {card.domain} specialist. {card.description}"
        if card.routing_cues:
            text += f" Typical job titles: {', '.join(card.routing_cues[:8])}."
        tools.append(ToolSpec(tool_name(card), text))
    return tools


def summarize(agent_id: str, result: CoachResult | None) -> str:
    """The tool message: what the specialist found, in counts and the posting's own requirement wording."""
    if result is None:
        return json.dumps({"agent": agent_id, "status": "failed"})
    return json.dumps(
        {
            "agent": agent_id,
            "status": "ok",
            "kind": result.kind,
            "suggestions": len(result.suggestions),
            "questions": len(result.questions),
            "requirements_covered": [s.requirement for s in result.suggestions][:6],
        },
        ensure_ascii=False,
    )


async def choose_specialist(
    cards: list[AgentCard], case: CareerCase, llm: ContentGenerator, steps: Sequence[ToolStep] = ()
) -> str | None:
    """The id of the next specialist the General agent calls among `cards`, or None if it calls none."""
    if not cards:
        return None
    chosen = await llm.choose_tool(
        DELEGATION_PROMPT,
        {"job_title": case.job_title, "career_goal": case.career_goal, "job_description": case.job_description},
        specialist_tools(cards),
        steps,
    )
    by_tool = {tool_name(card): card.id for card in cards}
    if chosen is not None and chosen not in by_tool:
        log_event(logger, logging.WARNING, "coach_delegation_unknown_tool")
    agent_id = by_tool.get(chosen or "")
    log_event(
        logger,
        logging.INFO,
        "coach_delegation",
        delegated=agent_id is not None,
        agent=agent_id or "general",
        step=len(steps) + 1,
    )
    return agent_id
