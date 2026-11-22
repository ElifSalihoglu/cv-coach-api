import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DEMO_JOBS, DEMO_MAIN_CV } from "./data/demo";
import { fakeApi, renderApp, setMobile } from "./test-utils";

let api: ReturnType<typeof fakeApi>;

beforeEach(() => {
  api = fakeApi();
  vi.stubGlobal("fetch", api.fetchMock);
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  setMobile(false);
});

const [demoA, demoB] = DEMO_JOBS;
const card = (name: RegExp) => screen.getByRole("article", { name });

test("the demo jobs share one main CV; their suggestions differ", () => {
  const ids = (d: (typeof DEMO_JOBS)[number]) => d.result.suggestions.map((s) => s.id);
  expect(ids(demoA)).not.toEqual(ids(demoB));
  for (const demo of DEMO_JOBS) {
    for (const s of demo.result.suggestions) {
      // every suggestion rests on a line that really is in the main CV
      const lines = DEMO_MAIN_CV.experiences.flatMap((e) => e.bullets).map((b) => b.id);
      expect(s.sources.every((r) => lines.includes(r.id))).toBe(true);
    }
  }
});

test("the home page never shows demo data", () => {
  renderApp("/");
  expect(screen.queryByText("Demo data")).not.toBeInTheDocument();
  expect(screen.queryByText(/Northwind Labs|Kestrel Analytics|Elçin/)).not.toBeInTheDocument();
});

test("Explore demo opens the sample results with a demo badge", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await user.click(screen.getByRole("link", { name: "Explore demo" }));

  expect(screen.getByText("Demo data")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AI Automation Engineer/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /Machine Learning Engineer/ })).toBeInTheDocument();
  expect(screen.getByText(/replace manual, error-prone workflows/)).toBeInTheDocument();
});

test("demo: suggestions appear without an upload or a request, and the preview starts as the main CV", async () => {
  const user = userEvent.setup();
  renderApp("/demo");

  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  expect(screen.getByRole("heading", { name: "Suggestions for this application" })).toBeInTheDocument();
  expect(api.fetchMock).not.toHaveBeenCalled();
  expect(screen.getByText(/Nothing accepted yet/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(DEMO_MAIN_CV.summary);
});

test("demo: accepting and rejecting changes only the draft; the PDF is exactly the draft", async () => {
  const user = userEvent.setup();
  renderApp("/demo");
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));

  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));
  await user.click(within(card(/Move up/)).getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(api.calls("/v1/coach/apply")).toHaveLength(2)); // after the accept, after the reject
  expect(Object.keys(api.body("/v1/coach/apply", 1).decisions)).toEqual(["summary"]);
  expect(api.body("/v1/coach/apply", 1).cv).toEqual(DEMO_MAIN_CV); // the main CV is what is sent, never a draft

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  await waitFor(() => expect(screen.getByTestId("cv-summary")).toHaveTextContent(/invoice triage agent that routes 12,000/));

  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  const sent = api.body("/v1/cv/render-pdf");
  expect(sent.cv.summary).toMatch(/invoice triage agent/);
  expect(sent.cv.experiences[1].bullets[0].id).toBe("exp2.b1"); // the rejected move did not happen
  expect(api.calls("/v1/coach/analyze")).toHaveLength(0);
});

test("demo: each job keeps its own decisions", async () => {
  const user = userEvent.setup();
  renderApp("/demo");
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));

  await user.click(screen.getByRole("button", { name: /Machine Learning Engineer/ }));
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  expect(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" })).toBeInTheDocument(); // undecided here

  await user.click(screen.getByRole("button", { name: /AI Automation Engineer/ }));
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument(); // still decided there
});

test("demo: a failed PDF download keeps the decisions and can be retried", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/render-pdf", () => new Response("nope", { status: 500 }));
  renderApp("/demo");
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await user.click(within(card(/Rewrite summary/)).getByRole("button", { name: "Accept" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Download PDF" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Download failed");
  expect(within(card(/Rewrite summary/)).getByText("✓ Accepted")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(api.calls("/v1/cv/render-pdf")).toHaveLength(2);
});
