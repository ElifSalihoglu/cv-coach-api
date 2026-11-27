"""
Fingerprints that say WHAT changed between two evaluation runs.

A score moves for a reason, and one combined hash cannot tell which. These are kept apart
on purpose:

- `config`:       the model name and how it is called (temperature, timeout, the LLM client code)
- `prompt`:       the agent's system prompt text (not the file, so a comment elsewhere does not count)
- `validation`:   the shared pipeline and gates plus this agent's own rules, gates and input
- `faithfulness`: the claim checks (numbers, seniority, skills) the validation relies on
- `fixture`:      this agent's synthetic candidates and postings

Per agent: changing the General agent leaves the IT agent's fingerprints alone, except where
they really share code (the core, which is part of every agent's `validation`).
Nothing here calls a model, so it is safe to compute anywhere.
"""
import hashlib
from pathlib import Path
from typing import Iterable

from app.services.llm_client import TEMPERATURE
from app.services.openai_setup import REQUEST_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[2]
_CAREERS = ROOT / "app" / "careers"

# Each agent's own evaluation data. A new agent adds its line here when it gets a fixture.
AGENT_FIXTURES: dict[str, list[str]] = {
    "it": ["app/evals/coach_fixture.py"],
    "general": ["app/evals/general_fixtures.py"],
}


def _digest(chunks: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()[:10]


def files_digest(paths: Iterable[Path]) -> str:
    """Hash of the files' contents, in a stable order (the path names are not part of it)."""
    return _digest(path.read_bytes() for path in sorted(paths))


def prompt_digest(prompt: str) -> str:
    return _digest([prompt.encode("utf-8")])


def config_digest(model: str) -> str:
    settings = f"model={model};temperature={TEMPERATURE};timeout={REQUEST_TIMEOUT_SECONDS}"
    return _digest([settings.encode(), (ROOT / "app/services/llm_client.py").read_bytes()])


def agent_fingerprint(agent_id: str, model: str) -> dict[str, str]:
    """The five fingerprints of one agent under one model."""
    from app.careers.agents.general import GENERAL_PROFILE  # imported here: keeps this module light
    from app.careers.assembly import build_default_registry

    # the General agent is not in the registry (it owns it); an unknown id fails loudly
    profile = GENERAL_PROFILE if agent_id == GENERAL_PROFILE.id else build_default_registry().get(agent_id).profile
    own_dir = _CAREERS / "agents" / agent_id
    return {
        "config": config_digest(model),
        "prompt": prompt_digest(profile.system_prompt),
        "validation": files_digest([
            *(_CAREERS / "core").glob("*.py"),
            *(p for p in own_dir.glob("*.py") if p.name != "prompt.py"),
        ]),
        "faithfulness": files_digest([_CAREERS / "core" / "claims.py"]),
        "fixture": files_digest(ROOT / p for p in AGENT_FIXTURES[agent_id]),
    }
