import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "./App";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import type { CoachMeta, CoachResult, CvChange, StructuredCV, Suggestion } from "./types";

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export const renderApp = (path = "/") =>
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

/** A small CV (one role, one line): enough for the review screen. */
export const MY_CV: StructuredCV = {
  name: "Kerem Aydın", email: "kerem@example.com", phone: "", location: "Ankara", links: [],
  summary: "Backend developer who ships reliable services.",
  experiences: [{ id: "exp1", employer: "Test A.Ş.", title: "Developer", start: "2020", end: "2024",
    location: "", bullets: [{ id: "exp1.b1", text: "Built a billing API." }] }],
  education: [], skills: ["Python"], projects: [], certifications: [], languages: [],
};

/** A CV with three lines in its role, so a line can be moved up. */
export const RICH_CV: StructuredCV = {
  ...MY_CV,
  experiences: [{ ...MY_CV.experiences[0], bullets: [
    { id: "exp1.b1", text: "Built a billing API." },
    { id: "exp1.b2", text: "Ran the on-call rotation." },
    { id: "exp1.b3", text: "Integrated partner webhooks and APIs." },
  ] }],
};

export const POSTING_TEXT = "Acme builds agents. You will ship LLM features.";

/** The routing the API reports for an IT posting matched by rules. */
export const IT_META: CoachMeta = {
  routing: { primary: "it", method: "rules", confidence: "high", reasons: ["title_cue:ai"] },
  runs: [{ agent_id: "it", status: "ok", duration_ms: 12, error_code: "" }],
  provenance: {},
};

// ---- canned coach answers for RICH_CV ----

export const PROMOTE: Suggestion = {
  id: "promote:exp1.b3", kind: "promote", requirement: "integrate partner webhooks", level: "required",
  sources: [{ id: "exp1.b3", where: "Developer — Test A.Ş.", text: "Integrated partner webhooks and APIs." }],
  support: "related", before: "Integrated partner webhooks and APIs.", after: "Integrated partner webhooks and APIs.",
  position: 3, rationale: "Related: integration work, not API design.", priority: 1,
};
export const SUMMARY: Suggestion = {
  id: "summary", kind: "summary", requirement: "ship LLM features", level: "required",
  sources: [{ id: "exp1.b1", where: "Developer — Test A.Ş.", text: "Built a billing API." }],
  support: "direct", before: RICH_CV.summary,
  after: "Backend developer who ships billing APIs and partner integrations to production.",
  position: null, rationale: "Leads with the billing API.", priority: 2,
};
export const REWRITE: Suggestion = {
  id: "rewrite:exp1.b2", kind: "rewrite", requirement: "keep tools reliable", level: "preferred",
  sources: [{ id: "exp1.b2", where: "Developer — Test A.Ş.", text: "Ran the on-call rotation." }],
  support: "direct", before: "Ran the on-call rotation.",
  after: "Ran the on-call rotation for the billing platform.", position: null,
  rationale: "Shows what the rotation covered.", priority: 3,
};

export const coachResult = (over: Partial<CoachResult> = {}): CoachResult => ({
  kind: "suggestions", focus: "", responsibilities: ["Ship LLM features"],
  requirements: [
    { text: "Ship LLM features", quote: "You will ship LLM features", level: "required" },
    { text: "Kubernetes", quote: "Kubernetes is a plus", level: "preferred" },
  ],
  tracks: [], suggestions: [PROMOTE, SUMMARY, REWRITE],
  questions: [{ id: "ask:kubernetes", requirement: "Kubernetes is a plus", level: "preferred", term: "Kubernetes",
    text: "The posting prefers Kubernetes. Your CV doesn't mention it. Have you used it?" }],
  dropped: 0, dropped_reasons: {}, meta: IT_META, ...over,
});

export const trackChoice = (): CoachResult => ({
  ...coachResult({ suggestions: [], questions: [] }),
  kind: "choose_focus",
  tracks: [
    { id: "ai", name: "AI", quote: "AI: ship LLM features", summary: "LLM features in production.",
      coverage: "strong", note: "", evidence: [
        { source_id: "exp1.b1", where: "Developer — Test A.Ş.", text: "Built a billing API.", why: "Shipped to production." },
        { source_id: "exp1.b2", where: "Developer — Test A.Ş.", text: "Ran the on-call rotation.", why: "Reliability." }] },
    { id: "python", name: "Python Backend", quote: "Python: build services", summary: "Backend services.",
      coverage: "strong", note: "", evidence: [
        { source_id: "exp1.b3", where: "Developer — Test A.Ş.", text: "Integrated partner webhooks and APIs.", why: "API integration." },
        { source_id: "exp1.b1", where: "Developer — Test A.Ş.", text: "Built a billing API.", why: "Backend API." }] },
    { id: "typescript", name: "TypeScript", quote: "TypeScript: dashboards", summary: "Dashboards.",
      coverage: "none", note: "No explicit TypeScript experience found in your CV.", evidence: [] },
  ],
});

/** A stand-in for the server's composition, enough to check what the screen shows and sends. */
function fakeApply(body: { cv: StructuredCV; suggestions: Suggestion[]; decisions: Record<string, { action: string; text?: string; confirmed_terms?: string[] }>; additions: { id: string; target: { id: string }; text: string }[] }) {
  const cv: StructuredCV = JSON.parse(JSON.stringify(body.cv));
  const changes: CvChange[] = [];
  const exp = cv.experiences[0];
  for (const [id, decision] of Object.entries(body.decisions)) {
    const s = body.suggestions.find((x) => x.id === id)!;
    const text = decision.action === "edit" ? decision.text! : s.after;
    if (s.kind === "summary") {
      cv.summary = text;
      changes.push({ kind: "summary", id: "summary", where: "Summary", before: s.before, after: text, detail: decision.action === "edit" ? "Edited by you" : "", user_added: Boolean(decision.confirmed_terms?.length) });
    } else if (s.kind === "rewrite") {
      exp.bullets.find((b) => b.id === s.sources[0].id)!.text = text;
      changes.push({ kind: "rewritten", id: s.sources[0].id, where: "Developer — Test A.Ş.", before: s.before, after: text, detail: decision.action === "edit" ? "Edited by you" : "", user_added: Boolean(decision.confirmed_terms?.length) });
    }
  }
  for (const [id, decision] of Object.entries(body.decisions)) {
    const s = body.suggestions.find((x) => x.id === id)!;
    if (decision && s.kind === "promote") {
      const i = exp.bullets.findIndex((b) => b.id === s.sources[0].id);
      const [line] = exp.bullets.splice(i, 1);
      exp.bullets.unshift(line);
      const existing = changes.find((c) => c.id === line.id);
      if (existing) { existing.kind = "moved_rewritten"; existing.detail = `Moved from ${s.position}th to 1st`; }
      else changes.push({ kind: "moved", id: line.id, where: "Developer — Test A.Ş.", before: "", after: line.text, detail: `Moved from ${s.position}th to 1st` });
    }
  }
  for (const a of body.additions) {
    const bullet = { id: `exp1.b${exp.bullets.length + 1}`, text: a.text };
    exp.bullets.push(bullet);
    changes.push({ kind: "added", id: bullet.id, where: "Developer — Test A.Ş.", before: "", after: a.text, detail: "", user_added: true });
  }
  return { cv, changes };
}

/** A fake API behind `fetch`; every call is recorded so tests can count model calls. */
export function fakeApi(options: { cv?: StructuredCV } = {}) {
  const fetchMock = vi.fn();
  const queues: Record<string, Array<() => Promise<Response> | Response>> = {};
  const defaults: Record<string, (body: any) => Response> = {
    "/v1/cv/extract-text": () => json({ filename: "cv.txt", text: "Kerem Aydın\nBackend developer" }),
    "/v1/cv/parse": () => json({ cv: options.cv ?? MY_CV, warnings: [] }),
    "/v1/coach/analyze": () => json(coachResult()),
    "/v1/coach/apply": (body) => json(fakeApply(body)),
    "/v1/coach/check": (body) =>
      json(/Kubernetes/.test(body.text)
        ? { claims: [{ kind: "skills", terms: ["Kubernetes"] }], message: "Your text mentions Kubernetes, which isn't in your CV." }
        : { claims: [], message: "" }),
    "/v1/cv/render-pdf": () => new Response(new Blob(["%PDF"]), { status: 200 }),
  };
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    const next = queues[url]?.shift();
    if (next) return next();
    const handler = defaults[url];
    if (!handler) throw new Error(`unexpected request ${url}`);
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    return handler(body);
  });
  return {
    fetchMock,
    /** Answer the next request to `url` with `reply` instead of the default. */
    once: (url: string, reply: () => Promise<Response> | Response) => {
      (queues[url] ??= []).push(reply);
    },
    calls: (url: string) => fetchMock.mock.calls.filter((c) => c[0] === url),
    body: (url: string, index = 0) => JSON.parse(fetchMock.mock.calls.filter((c) => c[0] === url)[index][1].body),
    /** Requests that reach the language model: only the analysis does. */
    modelCalls: () => fetchMock.mock.calls.filter((c) => c[0] === "/v1/coach/analyze" || c[0] === "/v1/cv/parse").length,
  };
}

type User = ReturnType<typeof userEvent.setup>;

/** Upload a file, analyze the text and confirm the structured CV: the CV is ready for a posting. */
export async function confirmCv(user: User) {
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "my-cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await user.click(await screen.findByRole("button", { name: "Confirm CV" }));
}

/** Fill the posting form and submit it. */
export async function submitPosting(
  user: User,
  fields: { title?: string; text?: string; goal?: string; company?: string; agent?: string } = {},
) {
  await user.type(screen.getByLabelText("Job title"), fields.title ?? "AI Engineer");
  await user.type(screen.getByLabelText("Job posting"), fields.text ?? POSTING_TEXT);
  if (fields.goal) await user.type(screen.getByLabelText(/Career goal/), fields.goal);
  if (fields.company) await user.type(screen.getByLabelText(/Company/), fields.company);
  if (fields.agent) await user.selectOptions(screen.getByLabelText(/^Agent/), fields.agent);
  await user.click(screen.getByRole("button", { name: "Analyze posting" }));
}
