# Architecture notes

How a request to `POST /v1/coach/analyze` is handled.

```
POST /v1/coach/analyze
  -> CareerOrchestrator.run(case)             routing, delegation, fallback; no analysis of its own
       |- DefaultRouter.route(signals)         rule-based; signals = title, posting, target (no CV)
       |- AgentRegistry.get(id)                the specialists (IT today)
       `- general CareerAgent                  analyses what no specialist clearly claims
  -> CareerAgent.analyze(case, llm)           card + DomainProfile, the same class for every agent
  -> AgentEngine.run(profile, case, llm)      prepare -> LLMClient.generate -> build_result (gates)
```

```
app/careers/
  orchestrator.py        CareerOrchestrator
  router.py              DefaultRouter: override -> one specialist's title cue -> general agent
  registry.py            AgentRegistry: specialists only; duplicate / unknown / malformed checks
  assembly.py            which agents this deployment uses (one line per specialist)
  core/
    agent.py             CareerAgent
    engine.py            AgentEngine (stateless, domain-agnostic) + DEFAULT_ENGINE
    profile.py           DomainProfile: prompt, input, gates, lexicon, limits
    state.py             CareerCase, RoutingSignals, AgentCard, RoutingDecision, AgentRun, CoachMeta
    evidence.py claims.py gates.py minimize.py   shared validation and data minimization
  agents/it/             IT agent: prompt, rules, gates, model input, card with routing cues
  agents/general/        general agent: prompt, rules, gates, model input, card
```

Responsibilities: `LLMClient` owns the model call (messages, provider, JSON parse, schema validation,
`LLMError` mapping, call log). `AgentEngine` owns what is sent, when to ask again, the evidence /
faithfulness / domain gates, result construction and the result log. The orchestrator owns who answers
and what happens when an agent fails. Nobody repeats another's job.

Routing: override (id or domain name; unknown = 422) -> a title or target-position cue of exactly one
specialist (its own `AgentCard.routing_cues`; the description may only veto) -> the general agent.
Failure: a model error keeps its HTTP mapping and is not retried with another agent; any other agent
error makes the general agent answer instead, recorded in `meta.runs` and `meta.routing.reasons`; if
the general agent itself fails the request fails.

Adding a domain: define a `DomainProfile` and an `AgentCard` (with its own routing cues) in
`agents/<domain>/`, add one `register` line in `assembly.py`. The engine, the orchestrator and the
router do not change (tests/test_career_orchestrator.py proves it with a real engine run).
