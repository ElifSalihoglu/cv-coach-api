"""
The evaluation tooling, checked without a single paid call.

`scripts/run_coach_eval.py` is the live evaluation. Here its plan mode, its refusal without a
key, and even its whole `--run` path are exercised against a scripted fake client; the real
OpenAI client class is replaced by one that fails the test if it is ever built.
"""
import argparse
import asyncio
import json
from types import SimpleNamespace

import openai
import pytest

from app.evals import fingerprint as fp
from app.models.coaching import CoachModelOutput
from tests.coach_scenarios import ai_output, python_output, tracks_output
from tests.test_coach_regression import _clear_output

FINGERPRINT_KEYS = ["config", "prompt", "validation", "faithfulness", "fixture"]


@pytest.fixture
def script(monkeypatch, tmp_path):
    import scripts.run_coach_eval as module

    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # .env may have loaded a real one at import
    built = []

    def forbidden(*args, **kwargs):
        built.append(kwargs)
        raise AssertionError("the real OpenAI client must not be built in a test")

    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    module.built = built
    return module


def args(**over) -> argparse.Namespace:
    return argparse.Namespace(**{"run": False, "repeat": 1, "budget": 12, "verbose": False, **over})


def test_the_plan_prints_what_would_happen_and_calls_and_writes_nothing(script, capsys, tmp_path):
    assert asyncio.run(script.run(args(repeat=2))) == 0
    out = capsys.readouterr().out

    assert "Plan only. Nothing was called." in out
    assert "planned without corrections: 8" in out  # 4 calls x 2 repetitions
    assert "Fingerprints: " + " | ".join(f"{k} " for k in FINGERPRINT_KEYS[:1]) in out
    for key in FINGERPRINT_KEYS:
        assert f"{key} " in out
    assert script.built == [] and not (tmp_path / "results").exists()


def test_run_without_an_api_key_stops_before_building_a_client(script, capsys):
    assert asyncio.run(script.run(args(run=True))) == 1
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().out
    assert script.built == []


class ScriptedClient:
    """Stands in for openai.AsyncOpenAI: answers from a queue, counts the calls."""

    answers: list[CoachModelOutput] = []
    calls = 0

    def __init__(self, **kwargs):
        assert kwargs.get("max_retries") == 0  # the evaluation must not hide retries from its budget
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        type(self).calls += 1
        content = type(self).answers.pop(0).model_dump_json()
        message = SimpleNamespace(content=content, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                               usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), model="fake")


def test_the_whole_run_path_works_against_a_scripted_client_within_its_budget(script, monkeypatch, capsys):
    ScriptedClient.answers, ScriptedClient.calls = [tracks_output(), ai_output(), python_output(), _clear_output()], 0
    monkeypatch.setattr(openai, "AsyncOpenAI", ScriptedClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    assert asyncio.run(script.run(args(run=True, budget=6))) == 0
    out = capsys.readouterr().out

    assert ScriptedClient.calls == 4 and "Model calls made: 4 of budget 6" in out
    (saved,) = (script.RESULTS_DIR).glob("coach_run_*.json")
    record = json.loads(saved.read_text(encoding="utf-8"))
    assert list(record["fingerprint"]) == FINGERPRINT_KEYS
    assert set(record["status"].values()) == {"done"}
    assert [c["status"] for c in record["calls"]] == ["ok"] * 4


def test_the_budget_is_a_hard_cap(script, monkeypatch):
    ScriptedClient.answers, ScriptedClient.calls = [tracks_output(), ai_output(), python_output(), _clear_output()], 0
    monkeypatch.setattr(openai, "AsyncOpenAI", ScriptedClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    asyncio.run(script.run(args(run=True, budget=2)))
    assert ScriptedClient.calls == 2


# ---- the fingerprints

def test_each_agent_has_five_separate_fingerprints_and_they_are_stable():
    first = fp.agent_fingerprint("it", "some-model")
    assert list(first) == FINGERPRINT_KEYS and first == fp.agent_fingerprint("it", "some-model")


def test_agents_differ_where_they_differ_and_agree_where_they_share_code():
    it, general = fp.agent_fingerprint("it", "m"), fp.agent_fingerprint("general", "m")
    for own in ("prompt", "validation", "fixture"):
        assert it[own] != general[own], own
    for shared in ("config", "faithfulness"):
        assert it[shared] == general[shared], shared


def test_a_different_model_changes_only_the_config_fingerprint():
    a, b = fp.agent_fingerprint("it", "model-a"), fp.agent_fingerprint("it", "model-b")
    assert [k for k in a if a[k] != b[k]] == ["config"]


def test_a_prompt_change_moves_the_prompt_fingerprint_alone():
    assert fp.prompt_digest("You are a coach.") != fp.prompt_digest("You are a coach!")


def test_an_unknown_agent_fails_loudly():
    from app.careers.registry import UnknownAgentError

    with pytest.raises(UnknownAgentError):
        fp.agent_fingerprint("plumbing", "m")
