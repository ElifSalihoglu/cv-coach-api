import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { IT_META, POSTING_TEXT, RICH_CV, coachResult, confirmCv, fakeApi, json, renderApp, submitPosting } from "./test-utils";
import type { CoachMeta } from "./types";

let api: ReturnType<typeof fakeApi>;

beforeEach(() => {
  api = fakeApi({ cv: RICH_CV });
  vi.stubGlobal("fetch", api.fetchMock);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => vi.unstubAllGlobals());

const GENERAL_META: CoachMeta = {
  routing: { primary: "general", method: "fallback", confidence: "low", reasons: ["no_clear_match"] },
  runs: [{ agent_id: "general", status: "ok", duration_ms: 9, error_code: "" }],
  provenance: {},
};
const agentPanel = () => screen.findByRole("region", { name: "How this analysis was made" });

// ---------------------------------------------------------------- the posting step

test("after the CV is confirmed the posting form comes first; a CV and a posting are all it needs", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);

  expect(await screen.findByRole("heading", { name: "Add the job posting" })).toBeInTheDocument();
  expect(screen.getByText(/CV confirmed/)).toBeInTheDocument();
  const analyze = screen.getByRole("button", { name: "Analyze posting" });
  expect(analyze).toBeDisabled();
  await user.type(screen.getByLabelText("Job title"), "AI Engineer");
  expect(analyze).toBeDisabled(); // the posting text is required too
  await user.type(screen.getByLabelText("Job posting"), POSTING_TEXT);
  expect(analyze).toBeEnabled();
});

test("the request carries the posting, the optional goal and the chosen agent; nothing else leaves", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user, { goal: "Backend developer", company: "Acme", agent: "general" });
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  const body = api.body("/v1/coach/analyze");
  expect(body).toMatchObject({
    job_title: "AI Engineer", job_description: POSTING_TEXT, focus: "",
    domain: "general", career_goal: "Backend developer",
  });
  expect(body.cv).toEqual(RICH_CV);
  expect(Object.keys(body).sort()).toEqual(["career_goal", "cv", "domain", "focus", "job_description", "job_title"]);
});

test("by default the agent is chosen automatically", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  expect(screen.getByLabelText(/^Agent/)).toHaveValue("");
  expect(screen.getByRole("option", { name: "Automatic (recommended)" })).toBeInTheDocument();
  await submitPosting(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.body("/v1/coach/analyze").domain).toBe("");
});

test("the company only reaches the PDF file name", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user, { company: "Acme" });
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  expect(api.body("/v1/cv/render-pdf")).toMatchObject({ company: "Acme", job_title: "AI Engineer" });
  expect(api.body("/v1/coach/analyze")).not.toHaveProperty("company");
});

// ---------------------------------------------------------------- which agent, and why

test("the panel names the agent and the posting words that chose it", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);

  const panel = await agentPanel();
  expect(panel).toHaveTextContent("IT agent");
  expect(panel).toHaveTextContent("matched “ai”");
  expect(panel).toHaveTextContent("Every proposal from the model passed our checks.");
});

test("no specialist matched: the General agent is named as the fallback", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () => json(coachResult({ meta: GENERAL_META })));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user, { title: "Staff Nurse" });

  const panel = await agentPanel();
  expect(panel).toHaveTextContent("General agent");
  expect(panel).toHaveTextContent("No specialist agent clearly matched this posting");
});

test("a forced agent is reported as the user's choice", async () => {
  const user = userEvent.setup();
  const forced: CoachMeta = { ...IT_META, routing: { primary: "it", method: "override", confidence: "high", reasons: ["override"] } };
  api.once("/v1/coach/analyze", () => json(coachResult({ meta: forced })));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user, { agent: "it" });
  expect(await agentPanel()).toHaveTextContent("You chose this agent.");
});

test("a specialist that failed is reported, and the agent that answered instead is named", async () => {
  const user = userEvent.setup();
  const recovered: CoachMeta = {
    routing: { primary: "general", method: "fallback", confidence: "low", reasons: ["agent_failed:it"] },
    runs: [
      { agent_id: "it", status: "failed", duration_ms: 3, error_code: "agent_error" },
      { agent_id: "general", status: "ok", duration_ms: 9, error_code: "" },
    ],
    provenance: {},
  };
  api.once("/v1/coach/analyze", () => json(coachResult({ meta: recovered })));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);
  const panel = await agentPanel();
  expect(panel).toHaveTextContent("The IT agent could not finish, so the General agent answered instead.");
});

test("what the checks removed is counted and explained in plain words", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () =>
    json(coachResult({ dropped: 3, dropped_reasons: { rewrite_unsupported_claim: 2, quote_not_in_posting: 1 } })));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);

  const panel = await agentPanel();
  expect(panel).toHaveTextContent("removed 3 proposals");
  expect(within(panel).getByText(/2 × reworded a line with a claim your CV does not support/)).toBeInTheDocument();
  expect(within(panel).getByText(/1 × quoted a requirement that is not in the posting/)).toBeInTheDocument();
});

// ---------------------------------------------------------------- states

test("while the analysis runs a status is shown, and the result replaces it", async () => {
  const user = userEvent.setup();
  let finish: (r: Response) => void = () => {};
  api.once("/v1/coach/analyze", () => new Promise<Response>((resolve) => { finish = resolve; }));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);

  expect(await screen.findByRole("status")).toHaveTextContent("Reading the posting against your CV");
  finish(json(coachResult()));
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("a failed analysis is reported and can be retried with the same posting", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  api.once("/v1/coach/analyze", () => json({ detail: "The career coach is unavailable." }, 503));
  await submitPosting(user);

  expect(await screen.findByRole("alert")).toHaveTextContent("The career coach is unavailable.");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.calls("/v1/coach/analyze")).toHaveLength(2);
  expect(api.body("/v1/coach/analyze", 1).job_description).toBe(POSTING_TEXT);
});

test("an unknown agent is reported with the API's own message", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  api.once("/v1/coach/analyze", () =>
    json({ detail: { code: "unknown_domain", message: "No agent for domain 'x'.", available: ["general", "it"] } }, 422));
  await submitPosting(user);
  expect(await screen.findByRole("alert")).toHaveTextContent("No agent for domain 'x'.");
});

test("a posting with nothing worth suggesting says so, and the PDF is still the main CV", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () => json(coachResult({ suggestions: [], questions: [] })));
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);
  expect(await screen.findByText(/Nothing worth changing for this focus/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled();
});

test("analyzing a different posting goes back to an empty form", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  await user.click(screen.getByRole("button", { name: "Analyze a different posting" }));
  expect(await screen.findByRole("heading", { name: "Add the job posting" })).toBeInTheDocument();
  expect(screen.getByLabelText("Job title")).toHaveValue("");
});

test("replacing the CV discards the suggestions made from the old one", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await confirmCv(user);
  await submitPosting(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  await user.click(screen.getByText(/CV confirmed/));
  await user.click(screen.getByRole("button", { name: "Upload a different CV" }));
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "new.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await user.click(await screen.findByRole("button", { name: "Confirm CV" }));

  expect(await screen.findByRole("heading", { name: "Add the job posting" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Suggestions for this application" })).not.toBeInTheDocument();
});

// ---------------------------------------------------------------- upload

test("upload errors and empty extraction guide the user", async () => {
  const user = userEvent.setup({ applyAccept: false });
  renderApp("/");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "cv.png", { type: "image/png" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unsupported file type");
  expect(api.fetchMock).not.toHaveBeenCalled();

  api.once("/v1/cv/extract-text", () => json({ filename: "scan.pdf", text: "" }));
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "scan.pdf", { type: "application/pdf" }));
  expect(await screen.findByText(/No text could be extracted/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analyze my CV" })).toBeDisabled();
});

test("a failed CV analysis keeps the reviewed text", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/parse", () => json({ detail: "CV coach is unavailable." }, 503));
  renderApp("/");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("CV coach is unavailable.");
  expect(screen.getByLabelText("CV text")).toHaveValue("Kerem Aydın\nBackend developer");
});
