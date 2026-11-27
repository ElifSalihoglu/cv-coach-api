"""
scripts/run_coach_eval.py, checked without a single paid call.

The real OpenAI client class is replaced by one that fails the test if it is ever built, except in
the tests that give it a scripted stand-in.
"""

import argparse
import asyncio
from types import SimpleNamespace

import openai
import pytest

from app.models.coaching import CoachModelOutput
from tests.fixtures.coach_scenarios import ai_output, python_output, tracks_output
from tests.test_coach_regression import _clear_output


@pytest.fixture
def script(monkeypatch):
    import scripts.run_coach_eval as module

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # .env may have loaded a real one at import
    built = []

    def forbidden(*args, **kwargs):
        built.append(kwargs)
        raise AssertionError("the real OpenAI client must not be built in a test")

    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    module.built = built
    return module


def args(**over) -> argparse.Namespace:
    return argparse.Namespace(**{"run": False, "budget": 8, **over})


def test_the_plan_prints_what_would_happen_and_calls_nothing(script, capsys):
    assert asyncio.run(script.run(args())) == 0
    out = capsys.readouterr().out

    assert "Plan only. Nothing was called." in out
    assert "call budget: 8" in out
    assert script.built == []


def test_run_without_an_api_key_stops_before_building_a_client(script, capsys):
    assert asyncio.run(script.run(args(run=True))) == 1
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().out
    assert script.built == []


class ScriptedClient:
    """Stands in for openai.AsyncOpenAI: answers from a queue and counts the calls."""

    answers: list[CoachModelOutput] = []
    calls = 0

    def __init__(self, **kwargs):
        assert kwargs.get("max_retries") == 0  # the budget must not hide SDK retries
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        type(self).calls += 1
        content = type(self).answers.pop(0).model_dump_json()
        message = SimpleNamespace(content=content, refusal=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            model="fake",
        )


def scripted(monkeypatch):
    ScriptedClient.answers = [tracks_output(), ai_output(), python_output(), _clear_output()]
    ScriptedClient.calls = 0
    monkeypatch.setattr(openai, "AsyncOpenAI", ScriptedClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")


def test_the_whole_run_path_works_against_a_scripted_client(script, monkeypatch, capsys):
    scripted(monkeypatch)

    assert asyncio.run(script.run(args(run=True, budget=6))) == 0
    out = capsys.readouterr().out

    assert ScriptedClient.calls == 4 and "Model calls made: 4 of budget 6" in out
    assert "NOT COMPLETED" not in out and "Checks passed:" in out


def test_the_budget_is_a_hard_cap(script, monkeypatch, capsys):
    scripted(monkeypatch)

    asyncio.run(script.run(args(run=True, budget=2)))

    assert ScriptedClient.calls == 2
    assert "NOT COMPLETED (BudgetExhausted)" in capsys.readouterr().out
