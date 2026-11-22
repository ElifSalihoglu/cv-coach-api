import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  PROMOTE, REWRITE, RICH_CV, SUMMARY, coachResult, fakeApi, json, renderApp, trackChoice,
} from "./test-utils";

let api: ReturnType<typeof fakeApi>;
type User = ReturnType<typeof userEvent.setup>;

beforeEach(() => {
  api = fakeApi({ cv: RICH_CV });
  vi.stubGlobal("fetch", api.fetchMock);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => vi.unstubAllGlobals());

/** Upload, confirm, search and ask for suggestions for the first job. */
async function openSuggestions(user: User) {
  renderApp("/cv");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "my-cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await user.click(await screen.findByRole("button", { name: "Confirm CV" }));
  await user.type(screen.getByLabelText("Role or keyword"), "AI Engineer");
  await user.type(screen.getByLabelText("City or remote"), "Berlin");
  await user.click(screen.getByRole("button", { name: "Search jobs" }));
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));
}

const card = (name: RegExp | string) => screen.getByRole("article", { name });
const accept = (user: User, name: RegExp) => user.click(within(card(name)).getByRole("button", { name: "Accept" }));
const lastApply = () => api.body("/v1/coach/apply", api.calls("/v1/coach/apply").length - 1);
const settled = () => waitFor(() => expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled());

// ---------------------------------------------------------------- focus

test("a posting with several tracks: the strong ones first, the others one click away, one more call after the choice", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () => json(trackChoice()));
  await openSuggestions(user);

  const strong = await screen.findByRole("list", { name: "Tracks backed by your CV" });
  expect(within(strong).getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual(["Choose AI", "Choose Python Backend"]);
  expect(within(strong).getAllByText(/Built a billing API\./).length).toBeGreaterThan(0); // evidence, from the CV

  const others = screen.getByText(/Other tracks in this posting \(1\)/).closest("details")!;
  expect(others).not.toHaveAttribute("open");
  expect(within(others).getByText("No explicit TypeScript experience found in your CV.")).toBeInTheDocument();
  expect(within(others).getByRole("button", { name: "Choose TypeScript" })).toBeInTheDocument(); // not hidden away
  expect(api.calls("/v1/coach/analyze")).toHaveLength(1);

  await user.click(within(strong).getByRole("button", { name: "Choose AI" }));
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.calls("/v1/coach/analyze")).toHaveLength(2);
  expect(api.body("/v1/coach/analyze", 1).focus).toBe("AI");
  expect(screen.getByText(/Focus:/)).toHaveTextContent("AI");
});

test("a clear posting needs no choice: one call and straight to suggestions", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.calls("/v1/coach/analyze")).toHaveLength(1);
  expect(screen.queryByText(/Which one are you applying for/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Focus:/)).not.toBeInTheDocument();
});

test("changing the focus and coming back reuses the earlier answer and keeps its decisions", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () => json(trackChoice()));
  await openSuggestions(user);
  await user.click(await screen.findByRole("button", { name: "Choose AI" }));
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  await accept(user, /Rewrite summary/);
  await settled();

  await user.click(screen.getByRole("button", { name: "Change focus" }));
  await user.click(screen.getByRole("button", { name: "Choose Python Backend" }));
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.calls("/v1/coach/analyze")).toHaveLength(3); // choice, AI, Python
  expect(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" })).toBeInTheDocument(); // separate draft

  await user.click(screen.getByRole("button", { name: "Change focus" }));
  await user.click(screen.getByRole("button", { name: "Choose AI" }));
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument();
  expect(api.calls("/v1/coach/analyze")).toHaveLength(3); // nothing asked again
});

test("a failed second call keeps the choice on screen", async () => {
  const user = userEvent.setup();
  api.once("/v1/coach/analyze", () => json(trackChoice()));
  api.once("/v1/coach/analyze", () => json({ detail: "The career coach is unavailable." }, 503));
  await openSuggestions(user);
  await user.click(await screen.findByRole("button", { name: "Choose AI" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("The career coach is unavailable.");
  expect(screen.getByRole("button", { name: "Choose Python Backend" })).toBeInTheDocument();
});

// ---------------------------------------------------------------- cards

test("each card shows the posting quote, the CV line it rests on, the level and whether the match is direct", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  const move = within(card(/Move up/));
  expect(move.getByText(/“integrate partner webhooks”/)).toBeInTheDocument();
  expect(move.getByText(/Developer — Test A\.Ş\.: “Integrated partner webhooks and APIs\.”/)).toBeInTheDocument();
  expect(move.getByText("Required")).toBeInTheDocument();
  expect(move.getByText("Related experience")).toBeInTheDocument();
  expect(move.getByText("Now line 3 in this role. Suggested: line 1.")).toBeInTheDocument();
  expect(move.queryByRole("button", { name: "Edit & accept" })).not.toBeInTheDocument(); // a move has no text

  const reword = within(card(/Reword suggestion/));
  expect(reword.getByText("Preferred")).toBeInTheDocument();
  expect(reword.queryByText("Related experience")).not.toBeInTheDocument();
  expect(reword.getByRole("button", { name: "Edit & accept" })).toBeInTheDocument();
});

test("the posting's responsibilities and its required and preferred skills are listed apart", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const panel = screen.getByText("What this posting asks for").closest("details")!;
  expect(within(panel).getByRole("heading", { name: "Main responsibilities" })).toBeInTheDocument();
  expect(within(panel).getByRole("heading", { name: "Required" }).nextElementSibling).toHaveTextContent("Ship LLM features");
  expect(within(panel).getByRole("heading", { name: "Preferred" }).nextElementSibling).toHaveTextContent("Kubernetes");
});

// ---------------------------------------------------------------- decisions

test("nothing is applied until the user decides: the preview and the PDF are the main CV", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  expect(api.calls("/v1/coach/apply")).toHaveLength(0);

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(RICH_CV.summary);
  expect(screen.getByText(/Nothing accepted yet/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  expect(api.body("/v1/cv/render-pdf").cv).toEqual(RICH_CV);
});

test("accept one, edit one, reject one: preview, What changed and PDF show the same final draft", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  await accept(user, /Move up/);
  const edit = within(card(/Reword suggestion/));
  await user.click(edit.getByRole("button", { name: "Edit & accept" }));
  await user.clear(edit.getByLabelText("Your wording"));
  await user.type(edit.getByLabelText("Your wording"), "Ran the on-call rotation for two years.");
  await user.click(edit.getByRole("button", { name: "Accept my wording" }));
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Reject" }));
  await settled();

  const sent = lastApply();
  expect(Object.keys(sent.decisions).sort()).toEqual(["promote:exp1.b3", "rewrite:exp1.b2"]);
  expect(sent.decisions["rewrite:exp1.b2"]).toEqual({ action: "edit", text: "Ran the on-call rotation for two years.", confirmed_terms: [] });
  expect(sent.cv).toEqual(RICH_CV); // the main CV goes in, untouched

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  const sheet = screen.getByRole("article", { name: "CV preview" });
  const lines = within(sheet).getAllByRole("listitem").map((li) => li.textContent?.replace(" (changed)", ""));
  expect(lines).toEqual(["Integrated partner webhooks and APIs.", "Built a billing API.", "Ran the on-call rotation for two years."]);
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(RICH_CV.summary); // the rejected summary is not in it

  expect(screen.getByText(/What changed \(2 changes\)/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  const pdf = api.body("/v1/cv/render-pdf").cv;
  expect(pdf.experiences[0].bullets.map((b: { text: string }) => b.text)).toEqual(lines);
  expect(pdf.summary).toBe(RICH_CV.summary);
});

test("deciding, undoing and downloading never reach the model", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const before = api.modelCalls();

  await accept(user, /Move up/);
  await accept(user, /Rewrite summary/);
  await user.click(within(card(/Move up/)).getByRole("button", { name: "Undo" }));
  await user.click(within(card(/Reword suggestion/)).getByRole("button", { name: "Reject" }));
  await user.click(within(card(/Reword suggestion/)).getByRole("button", { name: "Undo" }));
  await settled();
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));

  expect(api.modelCalls()).toBe(before);
});

test("undo puts a card back as it was, and undoing everything returns to the main CV", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  await accept(user, /Rewrite summary/);
  await settled();
  const applies = api.calls("/v1/coach/apply").length;
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Undo" }));

  expect(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" })).toBeInTheDocument();
  expect(api.calls("/v1/coach/apply")).toHaveLength(applies); // an empty draft needs no round trip
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(RICH_CV.summary);
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  expect(api.body("/v1/cv/render-pdf").cv).toEqual(RICH_CV);
});

test("a rejected card can be undone and then accepted", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Reject" }));
  expect(within(card(/Rewrite summary/)).getByText("Rejected")).toBeInTheDocument();
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Undo" }));
  await accept(user, /Rewrite summary/);
  await settled();
  expect(Object.keys(lastApply().decisions)).toEqual(["summary"]);
});

test("a move and a rewrite of the same line are independent: undo one, the other stays", async () => {
  const user = userEvent.setup();
  const sameLine = { ...REWRITE, id: "rewrite:exp1.b3", sources: PROMOTE.sources, before: PROMOTE.before,
    after: "Integrated partner webhooks and APIs for three payment providers." };
  api.once("/v1/coach/analyze", () => json(coachResult({ suggestions: [PROMOTE, sameLine], questions: [] })));
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  await accept(user, /Move up/);
  await accept(user, /Reword suggestion/);
  await settled();
  expect(Object.keys(lastApply().decisions).sort()).toEqual(["promote:exp1.b3", "rewrite:exp1.b3"]);
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByText(/What changed \(1 change\)/)).toBeInTheDocument(); // one record for the one line

  await user.click(within(card(/Move up/)).getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(Object.keys(lastApply().decisions)).toEqual(["rewrite:exp1.b3"]));
  const sheet = screen.getByRole("article", { name: "CV preview" });
  await waitFor(() => expect(within(sheet).getAllByRole("listitem")[2]).toHaveTextContent("three payment providers")); // reworded, back in place
});

test("a slow answer for an older decision never overwrites a newer one", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  let releaseFirst!: () => void;
  api.once("/v1/coach/apply", () => new Promise((resolve) => {
    releaseFirst = () => resolve(json({ cv: { ...RICH_CV, summary: "STALE" }, changes: [] }));
  }));
  await accept(user, /Move up/); // slow
  await accept(user, /Rewrite summary/); // fast, answers first
  await waitFor(() => expect(api.calls("/v1/coach/apply")).toHaveLength(2));
  releaseFirst();

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  await waitFor(() => expect(screen.getByTestId("cv-summary")).toHaveTextContent(/ships billing APIs/));
  expect(screen.getByTestId("cv-summary")).not.toHaveTextContent("STALE");
});

test("if applying a decision fails, the user is told and the decisions are kept", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  api.once("/v1/coach/apply", () => json({ detail: { code: "invalid_decision", message: "That CV line does not exist." } }, 422));
  await accept(user, /Rewrite summary/);

  expect(await screen.findByRole("alert")).toHaveTextContent("That CV line does not exist.");
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument();
});

// ---------------------------------------------------------------- Edit & accept

test("an edit with a claim the CV does not back up shows the difference and needs confirmation", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const summary = within(card(/Rewrite summary/));

  await user.click(summary.getByRole("button", { name: "Edit & accept" }));
  await user.type(summary.getByLabelText("Your wording"), " I run Kubernetes clusters.");
  await user.click(summary.getByRole("button", { name: "Accept my wording" }));

  const confirm = within(await screen.findByRole("group", { name: "Confirm new claims" }));
  expect(confirm.getByText(/Your CV does not|Your text says something your CV does not/i)).toBeInTheDocument();
  expect(confirm.getAllByText("Kubernetes", { selector: "mark" }).length).toBeGreaterThan(0); // listed, and marked in the difference
  expect(api.calls("/v1/coach/check")).toHaveLength(1);
  expect(api.body("/v1/coach/check")).toMatchObject({ kind: "summary", cv: { name: "Kerem Aydın" } });
  expect(api.calls("/v1/coach/apply")).toHaveLength(0); // nothing is accepted yet

  const add = confirm.getByRole("button", { name: "Add to my CV" });
  expect(add).toBeDisabled();
  await user.click(confirm.getByRole("checkbox"));
  await user.click(add);
  await settled();

  expect(lastApply().decisions.summary).toMatchObject({ action: "edit", confirmed_terms: ["Kubernetes"] });
  expect(screen.getByText(/What changed \(1 change\)/)).toBeInTheDocument();
  await user.click(screen.getByText(/What changed/));
  expect(screen.getByText(/Includes details you confirmed/)).toBeInTheDocument(); // recorded as added by the user
});

test("backing out of a confirmation accepts nothing", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const summary = within(card(/Rewrite summary/));
  await user.click(summary.getByRole("button", { name: "Edit & accept" }));
  await user.type(summary.getByLabelText("Your wording"), " Kubernetes.");
  await user.click(summary.getByRole("button", { name: "Accept my wording" }));
  await user.click(await screen.findByRole("button", { name: "Back to editing" }));

  expect(api.calls("/v1/coach/apply")).toHaveLength(0);
  expect(within(card(/Rewrite summary/)).getByLabelText("Your wording")).toBeInTheDocument();
});

// ---------------------------------------------------------------- questions

test("a question adds nothing until it is answered; the answer goes where the user says", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const question = within(card(/Question about Kubernetes/));
  expect(question.getByText("The posting prefers Kubernetes. Your CV doesn't mention it. Have you used it?")).toBeInTheDocument();
  expect(question.getByText("Preferred")).toBeInTheDocument();
  expect(api.calls("/v1/coach/apply")).toHaveLength(0);

  await user.click(question.getByRole("button", { name: "Yes, I used it…" }));
  await user.type(question.getByLabelText(/What did you do with Kubernetes/), "Deployed the billing API on Kubernetes.");
  expect(question.getByLabelText("Where did you use it?")).toHaveDisplayValue("Developer — Test A.Ş.");
  await user.click(question.getByRole("button", { name: "Review" }));

  const confirm = within(await screen.findByRole("group", { name: "Confirm new claims" }));
  await user.click(confirm.getByRole("checkbox"));
  await user.click(confirm.getByRole("button", { name: "Add to my CV" }));
  await settled();

  expect(lastApply().additions).toEqual([{
    id: "ask:kubernetes", target: { type: "experience", id: "exp1" },
    text: "Deployed the billing API on Kubernetes.", confirmed_terms: ["Kubernetes"],
  }]);
  expect(within(card(/Question about Kubernetes/)).getByText(/Added to Developer — Test A\.Ş\./)).toBeInTheDocument();

  await user.click(within(card(/Question about Kubernetes/)).getByRole("button", { name: "Undo" }));
  expect(within(card(/Question about Kubernetes/)).getByRole("button", { name: "No" })).toBeInTheDocument();
});

test("answering No notes it and adds nothing", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  await user.click(within(card(/Question about Kubernetes/)).getByRole("button", { name: "No" }));

  expect(within(card(/Question about Kubernetes/)).getByText("Noted: nothing added")).toBeInTheDocument();
  expect(api.calls("/v1/coach/apply")).toHaveLength(0);
});

test("an answer without any new claim is added right after the review", async () => {
  const user = userEvent.setup();
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });
  const question = within(card(/Question about Kubernetes/));
  await user.click(question.getByRole("button", { name: "Yes, I used it…" }));
  await user.type(question.getByLabelText(/What did you do with Kubernetes/), "Maintained the billing API.");
  await user.click(question.getByRole("button", { name: "Review" }));
  await settled();

  expect(screen.queryByRole("group", { name: "Confirm new claims" })).not.toBeInTheDocument();
  expect(lastApply().additions[0]).toMatchObject({ text: "Maintained the billing API.", confirmed_terms: [] });
});

test("a summary that draws on two CV lines shows both on its card", async () => {
  const user = userEvent.setup();
  const two = { ...SUMMARY, sources: [
    ...SUMMARY.sources,
    { id: "exp1.b3", where: "Developer — Test A.Ş.", text: "Integrated partner webhooks and APIs." },
  ] };
  api.once("/v1/coach/analyze", () => json(coachResult({ suggestions: [two], questions: [] })));
  await openSuggestions(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  const lines = within(card(/Rewrite summary/)).getAllByText(/Developer — Test A\.Ş\./);
  expect(lines).toHaveLength(2);
  expect(lines[0]).toHaveTextContent("Built a billing API.");
  expect(lines[1]).toHaveTextContent("Integrated partner webhooks and APIs.");
});
