import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DEMO_JOBS } from "./data/demo";
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

test("demo jobs share source experiences but differ in summary and highlights", () => {
  expect(demoA.cv.summary).not.toEqual(demoB.cv.summary);
  expect(demoA.cv.experiences.map((e) => e.id)).toEqual(demoB.cv.experiences.map((e) => e.id));
  expect(demoA.cv.experiences[0].bullets).not.toEqual(demoB.cv.experiences[0].bullets);
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

test("demo: tailoring is instant, needs no upload and makes no request; each job gets its own CV and PDF", async () => {
  const user = userEvent.setup();
  renderApp("/demo");

  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(demoA.cv.summary);
  expect(api.fetchMock).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  expect(api.body("/v1/cv/render-pdf")).toMatchObject({
    company: demoA.job.company, job_title: demoA.job.title, cv: { summary: demoA.cv.summary },
  });

  await user.click(screen.getByRole("button", { name: /Machine Learning Engineer/ }));
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent(demoB.cv.summary);
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(2));
  expect(api.body("/v1/cv/render-pdf", 1).cv.summary).toBe(demoB.cv.summary);
  expect(api.calls("/v1/cv/tailor")).toHaveLength(0);
});

test("demo: a failed PDF download keeps the CV ready and can be retried", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/render-pdf", () => new Response("nope", { status: 500 }));
  renderApp("/demo");
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await user.click(screen.getByRole("button", { name: "Download PDF" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Download failed");
  expect(screen.getByText("✓ CV ready for this job")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(api.calls("/v1/cv/render-pdf")).toHaveLength(2);
});
