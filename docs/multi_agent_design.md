# Multi-agent career coaching: design notes

Status: implemented except the items under "Next".

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

## Merger: choosing between suggestions that target the same CV line (design)

The merger never writes text; it only picks among suggestions the agents already validated.
Two suggestions collide when they have the same `id` (`promote:exp1.b4`, `summary`) or when a
promote and a rewrite name the same bullet. The primary agent gets no automatic priority.
Candidates are compared by this tuple, highest first, and the first difference decides:

1. **Evidence quality**: `support == "direct"` beats `"related"`; then more distinct cited
   source lines that really contain the requirement's distinctive terms.
2. **Requirement priority**: `required` beats `preferred`; a requirement that is specific to
   the chosen focus beats one both agents consider generic.
3. **Relevance**: share of the requirement quote's meaningful words found in the cited line
   (`evidence.meaningful`), so the card that answers the posting's own words wins.
4. Remaining tie: the lower model `priority`, then agent id alphabetically (stable, and
   deliberately not "primary first").

Provenance: the merged result records `agent` (agent id) on every suggestion and keeps the
losing candidate's agent id and reason in `meta` (codes only), so a person can see who
proposed what and why one was dropped. The `MAX_SUGGESTIONS` limit applies to the merged list.

## Validation gates per domain (design)

- **Shared, unchanged**: quote in posting, source id in CV, new numbers / seniority / skills,
  grounded questions, per-kind limits, `dropped_reasons` as codes.
- **Engineering**: a licence, registration or certification named in a text must exist in the
  CV's certifications (never inferred from the posting); a standard (ISO, IEC, ASME, DIN, TS)
  must appear in the CV; numbers are compared together with their unit (`250 kW` is not `250 kWh`)
  and with decimal comma/point normalised; sign-off or responsibility verbs (certified, approved,
  signed off, commissioned) need a CV line that says so; design/analysis claims need a design
  object in the CV, with an engineering word list instead of the IT one; tools (AutoCAD, ANSYS,
  PLC families) come from an engineering lexicon instead of the typographic default.
- **General**: conservative on purpose. Only `promote` and `summary`; no `rewrite` that adds
  vocabulary; a transferable-skill claim needs a cited line; any term that is jargon of a
  specific field and not in the CV is rejected. It never claims domain expertise, and when the
  posting clearly belongs to a specialist agent that is a routing signal, not something General
  patches over.

## Data minimization for professional evidence (design)

Today the IT input sends summary, skills, roles (id, title, employer, bullets with positions)
and projects. It never sends name, email, phone, location, links, dates or education, and a
test pins this. That stays frozen for the IT agent.

For fields where qualifications are the evidence, `core/minimize.py` gets more building
blocks, each opt-in per profile:

- `certifications`: `{id, name}` only. Issuer only when the posting names it. No credential or
  licence numbers, no dates. A pattern strips licence-number-like strings from names.
- `education`: `{id, degree, field}`; school and years are left out unless a requirement names
  an accredited programme, in which case only the accreditation-relevant fact is sent.
- `languages` as plain names.

Each new block needs: an entry in the allow-list file, ids so suggestions can cite it, the
evidence index extended from bullets to these items (so "source id in CV" covers them), and a
test that pins the exact payload keys and checks that no personal identifier is present.

## Next (not implemented)

7. Engineering agent (prompt, gates, lexicon, fixtures, its own cues in its card).
8. Merger and parallel primary/secondary run (at most two agents): `RoutingDecision.secondary` and
   `Orchestration.runs` are already in the API shape; `CareerOrchestrator.run` runs one agent today.
9. LLM-based routing, designed from real needs when it is implemented (input: posting and target position only).
