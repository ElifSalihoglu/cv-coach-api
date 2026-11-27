# Multi-agent career coaching: design notes

Status: implemented except the items under "Next". The General agent is the single entry point
and orchestrator; every specialist (today: IT) follows one standard and runs on one shared engine.

```
route /v1/coach/analyze
  -> CoachFacade (API call shape)
  -> GeneralAgent.handle(case, llm)          orchestration, delegation, fallback
       |- DefaultRouter.route(signals)        rule-based; signals = title, posting, target (no CV)
       |- AgentRegistry.get(id)               specialists only (the General agent owns the registry)
       `- GeneralAgent.analyze(case, llm)     its own analysis, same engine, General profile
  -> AgentEngine.run(profile, case, llm)      prepare -> LLMClient.generate -> build_result (gates)
```

```
app/careers/
  assembly.py            which specialists this deployment registers (one line per domain)
  facade.py              CoachFacade: the call shape the route (and legacy ITCareerCoach) share
  registry.py            AgentRegistry: specialists only, duplicate / unknown / malformed checks
  router.py              DefaultRouter: override -> one specialist's title cue -> General
  core/
    engine.py            AgentEngine (stateless, domain-agnostic) + DEFAULT_ENGINE
    base_agent.py        BaseCareerAgent (Protocol), SpecialistAgent (card + profile)
    profile.py           DomainProfile: prompt, input, gates, lexicon, limits
    state.py             CareerCase, RoutingSignals, AgentCard, RoutingDecision, AgentRun, CoachMeta
    evidence.py claims.py gates.py minimize.py   shared validation and data minimization
  agents/it/             IT specialist: prompt, rules, gates, model input, card with routing cues
  agents/general/        General agent: agent.py (handle / analyze), profile, prompt, rules, gates
app/services/job_coach.py   LEGACY shim (ITCareerCoach, build_result, ...); new code must not use it
```

Responsibilities: `LLMClient` owns the model call (messages, provider, JSON parse, schema validation,
`LLMError` mapping, call log). `AgentEngine` owns what is sent, when to ask again, the evidence /
faithfulness / domain gates, result construction and the result log. Neither repeats the other.

Routing: override (id or domain name; unknown = 422) -> a title or target-position cue of exactly one
specialist (its own `AgentCard.routing_cues`; the description may only veto) -> the General agent.
Failure: a model error keeps its HTTP mapping and is not retried with another agent; any other
specialist error makes the General agent answer instead, recorded in `meta.runs` and
`meta.routing.reasons`; if the General agent itself fails the request fails.

Adding a domain: define a `DomainProfile` and an `AgentCard` (with its own routing cues) in
`agents/<domain>/`, add one `register` line in `assembly.py`. The engine, the General agent and the
router do not change (tests/test_general_orchestration.py proves it with a real engine run).

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
   `Orchestration.runs` are already in the API shape; `GeneralAgent.handle` runs one agent today.
9. LLM-based routing, designed from real needs when it is implemented (input: posting and target position only).
