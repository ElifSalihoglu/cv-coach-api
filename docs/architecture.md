# Architecture notes

How a request to `POST /v1/coach/analyze` is handled.

```
POST /v1/coach/analyze
  -> CareerOrchestrator.run(case)             runs the hierarchy; not an LLM agent, no analysis of its own
       |- BudgetedLLM                          every model call of the request goes through it (max 8)
       |- DefaultRouter.route(override)        only when the caller names an agent
       |- delegation.choose_specialist         General agent + model tool calling: ask_<id> or no tool, in a loop
       |- AgentRegistry.get(id)                the specialists (IT, Healthcare, HR, Finance), one tool each
       |- AgentEngine.merge                    several results -> one, re-validated by code
       `- general CareerAgent                  main agent: answers itself when it calls no tool
  -> CareerAgent.analyze(case, llm)           card + DomainProfile, the same class for every agent
  -> AgentEngine.run(profile, case, llm)      prepare -> LLMClient.generate -> build_result (gates)
```

```
app/careers/
  orchestrator.py        CareerOrchestrator
  router.py              DefaultRouter: resolves an explicit agent request (override)
  delegation.py          the General agent's tool-calling decision; one tool per registered specialist
  budget.py              BudgetedLLM: per-request limit on model calls
  registry.py            AgentRegistry: specialists only; duplicate / unknown / malformed checks
  assembly.py            which agents this deployment uses (one line per specialist)
  core/
    agent.py             CareerAgent
    engine.py            AgentEngine (stateless, domain-agnostic) + DEFAULT_ENGINE
    profile.py           DomainProfile: prompt, input, gates, lexicon, limits
    state.py             CareerCase, AgentCard, RoutingDecision, AgentRun, CoachMeta
    evidence.py claims.py gates.py minimize.py   shared validation and data minimization
  agents/it/             IT agent: prompt, rules, gates, model input, card with example titles
  agents/general/        general agent: prompt, rules, gates, model input, card
```

Responsibilities: `LLMClient` owns the model call (messages, provider, JSON parse, schema validation,
`LLMError` mapping, call log). `AgentEngine` owns what is sent, when to ask again, the evidence /
faithfulness / domain gates, result construction and the result log. The orchestrator owns who answers
and what happens when an agent fails. Nobody repeats another's job.

Hierarchy: the General agent is the main agent. Without an override it runs a loop of at most two specialist
calls. Each round is one model call that gets the posting title, the target position and the posting text
(never the CV) plus one tool per specialist not yet called, built from the specialist's card (`ask_<id>`).
If the model calls a tool, that specialist runs on the shared engine; a short JSON summary of its result
(counts and the posting's own requirement wording, no CV text) goes back as the tool message, and the
model calls another specialist or none (it is done). A name that is not on offer ends the loop. If no
specialist was called, the General agent analyses the posting itself.
Result: one specialist's validated result is returned unchanged. Two are merged by `AgentEngine.merge`, with
no model writing: items in call order (the first agent keeps one both made), each re-checked against the
posting and the CV with the gates of the agent that made it, then the General agent's per-kind and total
limits are applied. What fails is dropped and counted. A result that asks the user to choose a focus ends
the loop and is returned alone. There is no separate LLM orchestrator. Override (id or domain name;
unknown = 422) skips the loop. `GET /v1/coach/agents` lists the registry for the UI.
Budget: at most 8 model calls per request (2 decisions, 2 x 2 specialist calls, 2 General calls after
failures) and 2 specialists; the call that would exceed it is refused before it is made (500).
Failure: a model error keeps its HTTP mapping and is not retried with another agent; any other agent
error makes the general agent answer instead, recorded in `meta.runs` and `meta.routing.reasons`; if
the general agent itself fails the request fails.

Adding a domain: define a `DomainProfile` and an `AgentCard` (example titles go in the card) in
`agents/<domain>/`, add one `register` line in `assembly.py`. The engine, the orchestrator, the
General agent and the delegation code do not change (tests/test_career_orchestrator.py proves it with a real engine run).
