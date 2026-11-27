# CV Coach

CV Coach helps a candidate present an existing CV for one job posting. A language model proposes what to
move up, reword or ask about; code then checks every proposal against the posting and the CV, drops the ones
that add facts the CV does not support, and leaves the final decision to the user.

It is a FastAPI backend with a React frontend. Most of the logic is in the backend: how the model's output is
constrained, checked and kept under the user's control.

## Features

- Upload a CV (PDF, DOCX or TXT). The text is extracted and shown for review, then structured by one model
  call. The user confirms the structured CV.
- Paste a job posting (optionally a career goal or a chosen agent). The system picks an agent and returns
  suggestions (move a line up, reword a line, rewrite the summary) plus questions about requirements the CV
  does not mention.
- Each suggestion shows the posting line, the CV lines it rests on, and why.
- The user accepts, edits or rejects each one. A preview shows exactly what the PDF will contain, and the PDF
  is rendered on the server.

![Analysis with agent information and sources](docs/images/02-analysis.png)

![Updated CV preview (built-in demo, synthetic data)](docs/images/04-preview.png)

## Architecture

```mermaid
flowchart LR
    UI[React frontend] -->|extract-text, parse, render-pdf| CV[CV endpoints]
    UI -->|analyze| ORCH[CareerOrchestrator]
    ORCH --> ROUTER[DefaultRouter<br/>rule-based]
    ORCH --> REG[AgentRegistry<br/>specialists]
    REG --> IT[IT agent]
    ORCH --> GEN[General agent]
    IT --> ENGINE[AgentEngine]
    GEN --> ENGINE
    ENGINE --> LLM[LLMClient<br/>OpenAI chat completions]
    ENGINE --> GATES[Evidence, faithfulness<br/>and domain gates]
    UI -->|check, apply| APPLY[Deterministic apply<br/>no model]
```

- `CareerOrchestrator` routes a case, runs one agent, records who answered, and falls back to the general
  agent. `DefaultRouter` chooses by rules; `AgentRegistry` holds the specialists.
- `CareerAgent` is an `AgentCard` plus a `DomainProfile` (prompt, model input, gates, word lists). The IT agent
  and the general agent are two instances. Adding a specialist is a registry entry plus its profile.
- `AgentEngine` is stateless and shared: prepare the input, call the model, apply the gates, build the result.

More detail: [docs/architecture.md](docs/architecture.md).

## Agents and validation

- **Rule-based routing, no model.** If exactly one specialist's phrases appear in the job title or career
  goal, it is chosen; the posting text can only veto. Otherwise the general agent answers. If a specialist
  fails for a reason other than the model, the general agent answers instead; model errors are not retried
  with another agent.
- **Domain-specific agents.** Different prompts, model inputs and gates. The IT agent refuses a summary that
  claims "designed REST APIs" when no CV line says so; the general agent refuses licences, certifications or
  degrees the CV does not list.
- **Structured output.** The model is asked for JSON and the answer is validated against a Pydantic schema.
  An unusable answer becomes an error, not a partial result.
- **Evidence grounding.** Every suggestion carries a quote that must appear in the posting and cites CV lines
  by id; unknown ids are dropped. The CV lines shown next to a suggestion are copied by code, and a "direct"
  match claimed by the model is downgraded to "related" when the line lacks the requirement's key terms.
- **Faithfulness.** A draft text may not add numbers, seniority words, or posting skills the CV does not
  contain. Proposals that fail a gate are removed, and the response says how many and why.
- **Human in the loop.** Nothing changes until the user accepts it. An edited text that makes a new claim
  needs an explicit confirmation. Applying decisions, checking text and rendering the PDF never call a model.
- **Privacy.** The model input is a fixed set of fields without name, contact details, links or dates. Logs
  contain event names, counts and reason codes, not CV or posting text.

## Tech stack

Python 3.11, FastAPI, Pydantic, OpenAI SDK (chat completions), pypdf, python-docx, fpdf2. React 19, TypeScript,
Vite. pytest, Vitest, Ruff, GitHub Actions.

## Setup and demo

Requirements: Python 3.11+, Node 20.19+ or 22.12+.

```powershell
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
python -m uvicorn app.main:app --reload
```

```powershell
cd frontend
npm ci
npm run dev                       # http://localhost:5173, proxies /v1 to 127.0.0.1:8000
```

Set `OPENAI_API_KEY` in `.env` (`OPENAI_MODEL` defaults to `gpt-4.1-mini`) and restart the server. Without a
key the API starts, but CV structuring and analysis answer 503.

**Demo:** open `http://localhost:5173/demo`. It shows two pre-recorded analyses for synthetic candidates. No
model is called and no API key is needed; accepting suggestions and downloading the PDF use the real API, so
the backend must be running.

## Tests

```powershell
python -m pytest                  # no API key, no network
python -m ruff check .

cd frontend
npm test
npx tsc --noEmit
npm run build
```

CI runs the same commands without an API key. Backend tests use fake model clients, and
`tests/golden/coach_regression.json` pins the IT agent's prompt, model input and validation results.

## Known limitations

- Two agents only (IT and general). Routing matches mostly English phrases in the job title or career goal.
- Validation is rule-based. It reduces unsupported claims but does not prove their absence; skill detection is
  heuristic and free text that names no skill is not checked.
- The model may ask no questions about requirements the CV lacks. Real-model behaviour was checked only on two
  synthetic cases, so there are no quality or cost figures.
- No OCR (scanned PDFs are not supported). CV and posting text are sent to OpenAI.
- Local development project: no authentication, no rate limiting, and the frontend keeps state in memory only.
  Run `pip-audit` and `npm audit` again before deploying.

## License

MIT, see [LICENSE](LICENSE). The bundled DejaVu fonts have their own license in `app/assets/fonts/LICENSE`.
