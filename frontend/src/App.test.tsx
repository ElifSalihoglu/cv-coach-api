import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DEMO_SCENARIOS } from "./data/demo";
import { fakeApi, renderApp } from "./test-utils";

let api: ReturnType<typeof fakeApi>;

beforeEach(() => {
  api = fakeApi();
  vi.stubGlobal("fetch", api.fetchMock);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => vi.unstubAllGlobals());

const [itScenario, nurseScenario] = DEMO_SCENARIOS;
const card = (name: RegExp) => screen.getByRole("article", { name });

test("every demo suggestion rests on a line that really is in its scenario's CV", () => {
  for (const scenario of DEMO_SCENARIOS) {
    const lines = scenario.cv.experiences.flatMap((e) => e.bullets);
    for (const s of scenario.result.suggestions) {
      for (const source of s.sources) {
        expect(lines.find((b) => b.id === source.id)?.text).toBe(source.text);
      }
    }
    expect(scenario.result.meta).not.toBeNull();
  }
});

test("the home page starts with the upload and never shows demo data", () => {
  renderApp("/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Tailor your CV to a job");
  expect(screen.getByLabelText(/Upload your CV/)).toBeInTheDocument();
  expect(screen.queryByText("Sample data")).not.toBeInTheDocument();
  expect(screen.queryByText(/Northwind Labs|Elçin|Aylin/)).not.toBeInTheDocument();
});

test("the demo is one click away and says plainly that no model is called", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await user.click(screen.getAllByRole("link", { name: "Explore the demo" })[1]);

  expect(screen.getByText("Sample data")).toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent(/pre-recorded.*no language model is called/);
  expect(screen.getByRole("heading", { name: itScenario.posting.title })).toBeInTheDocument();
  expect(api.fetchMock).not.toHaveBeenCalled();
});

test("demo: the panel names the agent, why it was chosen, and what the checks removed", async () => {
  const user = userEvent.setup();
  renderApp("/demo");

  const panel = screen.getByRole("region", { name: "How this analysis was made" });
  expect(panel).toHaveTextContent("IT agent");
  expect(panel).toHaveTextContent(/matched “ai”/);
  expect(panel).toHaveTextContent(/removed 2 proposals/);
  expect(within(panel).getByText(/a claim your CV does not support/)).toBeInTheDocument();
  expect(within(panel).getByText(/a requirement that is not in the posting/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: nurseScenario.label }));
  const nursePanel = screen.getByRole("region", { name: "How this analysis was made" });
  expect(nursePanel).toHaveTextContent("General agent");
  expect(nursePanel).toHaveTextContent(/No specialist agent clearly matched/);
  expect(nursePanel).toHaveTextContent(/removed 1 proposal /);
});

test("demo: each suggestion shows the posting line and the CV line it rests on", () => {
  renderApp("/demo");
  const summary = card(/Rewrite summary/);
  expect(summary).toHaveTextContent("Experience shipping automation or LLM features to production");
  expect(summary).toHaveTextContent(/Senior Software Engineer — Boğaz Yazılım: “Built an LLM-based invoice triage agent/);
});

test("demo: suggestions appear without a request, and the preview starts as the main CV", async () => {
  const user = userEvent.setup();
  renderApp("/demo");

  expect(screen.getByRole("heading", { name: "Suggestions for this application" })).toBeInTheDocument();
  expect(api.fetchMock).not.toHaveBeenCalled();
  expect(screen.getByText(/Nothing accepted yet/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(itScenario.cv.summary);
});

test("demo: accepting and rejecting changes only the draft; the PDF is exactly the draft", async () => {
  const user = userEvent.setup();
  renderApp("/demo");

  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));
  await user.click(within(card(/Move up/)).getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(api.calls("/v1/coach/apply")).toHaveLength(2)); // after the accept, after the reject
  expect(Object.keys(api.body("/v1/coach/apply", 1).decisions)).toEqual(["summary"]);
  expect(api.body("/v1/coach/apply", 1).cv).toEqual(itScenario.cv); // the main CV is what is sent, never a draft

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  await waitFor(() => expect(screen.getByTestId("cv-summary")).toHaveTextContent(/invoice triage agent that routes 12,000/));

  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  const sent = api.body("/v1/cv/render-pdf");
  expect(sent.cv.summary).toMatch(/invoice triage agent/);
  expect(sent.cv.experiences[1].bullets[0].id).toBe("exp2.b1"); // the rejected move did not happen
  expect(sent.company).toBe("Northwind Labs");
  expect(api.calls("/v1/coach/analyze")).toHaveLength(0);
});

test("demo: switching scenario starts with no decisions", async () => {
  const user = userEvent.setup();
  renderApp("/demo");
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: nurseScenario.label }));
  expect(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: itScenario.label }));
  expect(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" })).toBeInTheDocument();
});

test("demo: a failed PDF download keeps the decisions and can be retried", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/render-pdf", () => new Response("nope", { status: 500 }));
  renderApp("/demo");
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Download PDF" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Download failed");
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(api.calls("/v1/cv/render-pdf")).toHaveLength(2);
});
