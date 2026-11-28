"""
The parts of an agent prompt that do not depend on the field: how the answer is shaped. The specialist
agents added after the IT and General agents build their prompts from this plus field-specific text.
(The IT and General prompts are pinned by tests and stay whole.)
"""

INPUT_AND_OUTPUT = """
You receive a JSON object with:
- job_title and job_description: the posting
- focus: the role the candidate chose (empty if none yet)
- posting_offers_choice: computed by us; false means the posting has one role
- candidate: summary, skills, experiences and more. Each experience has an id, title, employer and
  bullets; each bullet has an id, its position (1 = first in its role) and its text. Education entries
  (id, degree, details) and certifications (id, name) carry no school, issuer, dates or numbers; never
  ask for them and never invent them.

Every requirement, track and suggestion carries a quote: a short passage copied exactly,
character for character, from job_description. Requirements have level "required" (must have,
"you hold", "minimum") or "preferred" ("nice to have", "plus"). Keep the two apart.

Focus. If posting_offers_choice is false never return "choose_focus". If focus is given, write for
that role only: mode "suggestions", focus = that name. If focus is empty and the posting lets the
applicant pick among several distinct roles, return mode "choose_focus" and list EVERY role in
tracks (name, quote, summary, evidence: bullets that themselves show work for it, each with a short
why), with no suggestions. Otherwise return mode "suggestions" and name the focus.

Suggestions (at most 5, most useful first) are of three kinds:
- "promote": move one bullet to the top of its role. source_ids = [that bullet id]. Never for a
  bullet at position 1. No text.
- "rewrite": at most ONE, only when new wording makes real, source-backed substance visible. `after`
  uses only facts of the source bullet. Never a wording-only change.
- "summary": at most ONE. 2-3 sentences using only facts from the candidate's CV. No self-labels or
  filler.
Each has requirement_quote, level, source_ids, support, rationale (one short plain sentence) and
priority (1 = most useful). support is "direct" only when a bullet shows the very duty or tool the
requirement names, otherwise "related"; for "related" never write "directly" or "exactly" and do not
use the requirement's exact term in any text you write.

Questions (mode "suggestions"). List, before the suggestions, at most 2 requirement terms that are in
job_description and appear nowhere in the candidate's CV (required before preferred): requirement_quote,
level and term (the word exactly as in the posting). Never ask about something the posting does not
mention.

Faithfulness (most important): the CV is the only source of facts. The posting is NOT evidence that
the candidate has a qualification, tool, seniority, number or result. Never add a number, percentage,
team size, budget or seniority claim that is not in the source. Keep the language of the CV in any CV
text you write. Write rationale in English.

Respond with valid JSON only, using exactly this structure:
{
  "mode": "suggestions" | "choose_focus",
  "focus": "short name of the focus, or empty",
  "responsibilities": ["..."],
  "requirements": [{"text": "...", "quote": "...", "level": "required" | "preferred"}],
  "tracks": [{"name": "...", "quote": "...", "summary": "...",
              "evidence": [{"source_id": "exp1.b2", "why": "..."}]}],
  "questions": [{"requirement_quote": "...", "level": "required" | "preferred", "term": "..."}],
  "suggestions": [{"kind": "promote" | "rewrite" | "summary",
                   "requirement_quote": "...", "level": "required" | "preferred",
                   "source_ids": ["exp1.b2"], "support": "direct" | "related",
                   "after": "...", "rationale": "...", "priority": 1}]
}
"""
