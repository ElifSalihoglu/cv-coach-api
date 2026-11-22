import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { JOB_A, MY_CV, fakeApi, json, renderApp, setMobile } from "./test-utils";

let api: ReturnType<typeof fakeApi>;
type User = ReturnType<typeof userEvent.setup>;

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

async function search(user: User, query = "AI Engineer", city = "Berlin") {
  await user.clear(screen.getByLabelText("Role or keyword"));
  await user.type(screen.getByLabelText("Role or keyword"), query);
  await user.clear(screen.getByLabelText("City or remote"));
  await user.type(screen.getByLabelText("City or remote"), city);
  await user.click(screen.getByRole("button", { name: "Search jobs" }));
}

const jobCard = (title: RegExp) => screen.getByRole("button", { name: title });

async function uploadAndConfirm(user: User) {
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "my-cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await user.click(await screen.findByRole("button", { name: "Confirm CV" }));
}

test("home: the search form comes first and a CV is not required", () => {
  renderApp("/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Find your next role");
  expect(screen.getByLabelText("Role or keyword")).toBeInTheDocument();
  expect(screen.getByLabelText("City or remote")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Search jobs" })).toBeInTheDocument();
  const card = screen.getByRole("complementary", { name: "Your CV" });
  expect(within(card).getByRole("link", { name: "Upload CV" })).toHaveAttribute("href", "/cv");
});

test("acceptance (desktop): search without a CV, read a posting, tailor, upload once, get preview and PDF for each job", async () => {
  const user = userEvent.setup();
  renderApp("/");

  // 1. Search with no CV: only the search endpoint is called, no model.
  await search(user);
  await screen.findByRole("list", { name: "Search results" });
  expect(api.body("/v1/jobs/search")).toEqual({ query: "AI Engineer", city: "Berlin" });
  expect(api.fetchMock).toHaveBeenCalledTimes(1);

  // 2. Cards show position, company and location; the first job is open on the right.
  expect(jobCard(/AI Engineer/)).toHaveTextContent("Acme");
  expect(jobCard(/AI Engineer/)).toHaveTextContent("Berlin");
  expect(screen.getByText(/You will ship LLM features/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View original posting" })).toHaveAttribute("href", JOB_A.source_url);

  // Browsing postings costs nothing.
  await user.click(jobCard(/ML Engineer/));
  expect(screen.getByText("Beta trains ranking models.")).toBeInTheDocument();
  await user.click(jobCard(/AI Engineer/));
  expect(api.fetchMock).toHaveBeenCalledTimes(1);

  // 3. Tailor without a CV: the upload pages open.
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  expect(screen.getByRole("heading", { name: "Upload your CV" })).toBeInTheDocument();

  // 4. Upload, review, analyze, confirm: back on the same job, tailoring starts by itself.
  await uploadAndConfirm(user);
  expect(await screen.findByText("✓ CV ready for this job")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "AI Engineer" })).toBeInTheDocument();
  expect(api.calls("/v1/cv/tailor")).toHaveLength(1);
  expect(api.body("/v1/cv/tailor")).toMatchObject({
    job_title: "AI Engineer", job_description: JOB_A.job_description, cv: { name: "Kerem Aydın" },
  });

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent("Tailored for AI Engineer.");
  await user.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.calls("/v1/cv/render-pdf")).toHaveLength(1));
  expect(api.body("/v1/cv/render-pdf")).toMatchObject({
    company: "Acme", job_title: "AI Engineer", cv: { summary: "Tailored for AI Engineer." },
  });

  // 5. Second job: no new upload, one more tailoring call.
  await user.click(jobCard(/ML Engineer/));
  expect(screen.queryByRole("heading", { name: "Upload your CV" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  expect(await screen.findByText("✓ CV ready for this job")).toBeInTheDocument();
  expect(api.calls("/v1/cv/tailor")).toHaveLength(2);
  expect(api.body("/v1/cv/tailor", 1).job_title).toBe("ML Engineer");
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent("Tailored for ML Engineer.");

  // 6. Back to the first job: its CV and PDF are still there, with no new model call.
  await user.click(jobCard(/AI Engineer/));
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveTextContent("Tailored for AI Engineer.");
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled();
  expect(api.calls("/v1/cv/tailor")).toHaveLength(2);
  expect(api.calls("/v1/cv/extract-text")).toHaveLength(1);
  expect(api.calls("/v1/cv/parse")).toHaveLength(1);
  expect(jobCard(/ML Engineer/)).toHaveTextContent("CV ready");
});

test("the CV card follows the CV: file name and Review CV once confirmed", async () => {
  const user = userEvent.setup();
  renderApp("/cv");
  await uploadAndConfirm(user);
  const card = screen.getByRole("complementary", { name: "Your CV" });
  expect(card).toHaveTextContent("my-cv.txt");
  expect(within(card).getByRole("link", { name: "Review CV" })).toBeInTheDocument();

  await user.click(within(card).getByRole("link", { name: "Review CV" }));
  expect(screen.getByRole("heading", { name: "Kerem Aydın" })).toBeInTheDocument();
});

test("with a CV already confirmed, Tailor my CV works at once", async () => {
  const user = userEvent.setup();
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));
  expect(await screen.findByText("✓ CV ready for this job")).toBeInTheDocument();
  expect(api.calls("/v1/cv/tailor")).toHaveLength(1);
});

test("searching state is shown in the results section and blocks a second search", async () => {
  const user = userEvent.setup();
  let release!: () => void;
  api.once("/v1/jobs/search", () => new Promise((resolve) => { release = () => resolve(json({ jobs: [JOB_A] })); }));
  renderApp("/");
  await search(user);

  expect(await screen.findByText(/Searching Indeed/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();
  release();
  expect(await screen.findByRole("list", { name: "Search results" })).toBeInTheDocument();
});

test("no results: says so", async () => {
  const user = userEvent.setup();
  api.once("/v1/jobs/search", () => json({ jobs: [] }));
  renderApp("/");
  await search(user, "Underwater Welder", "Oslo");
  expect(await screen.findByText(/No jobs found for “Underwater Welder” in Oslo/)).toBeInTheDocument();
});

test("Indeed verification: shows the real status in English; the CV and form stay", async () => {
  const user = userEvent.setup();
  api.once("/v1/jobs/search", () =>
    json({ detail: { code: "human_verification", message: "Indeed insan doğrulaması istedi." } }, 503));
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Indeed asked for a human verification.");
  expect(alert).not.toHaveTextContent("doğrulaması");
  expect(screen.getByLabelText("Role or keyword")).toHaveValue("AI Engineer");
  expect(screen.getByRole("complementary", { name: "Your CV" })).toHaveTextContent("my-cv.txt");

  await user.click(screen.getByRole("button", { name: "Search jobs" })); // search again, no re-upload
  expect(await screen.findByRole("list", { name: "Search results" })).toBeInTheDocument();
  expect(api.calls("/v1/cv/extract-text")).toHaveLength(1);
});

test("a posting without a description cannot be tailored", async () => {
  const user = userEvent.setup();
  api.once("/v1/jobs/search", () =>
    json({ jobs: [{ ...JOB_A, job_description: "", status: "missing_description" }] }));
  renderApp("/");
  await search(user);
  expect(await screen.findByText(/No job description was found/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tailor my CV" })).toBeDisabled();
});

test("a failed tailoring is reported on that job and can be retried", async () => {
  const user = userEvent.setup();
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);
  api.once("/v1/cv/tailor", () => json({ detail: "CV coach is unavailable." }, 503));
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("CV coach is unavailable.");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("✓ CV ready for this job")).toBeInTheDocument();
  expect(api.calls("/v1/cv/tailor")).toHaveLength(2);
});

test("mobile: tapping a job opens its details; going back keeps the query and results", async () => {
  setMobile(true);
  const user = userEvent.setup();
  renderApp("/");
  await search(user);

  const list = await screen.findByRole("list", { name: "Search results" });
  expect(screen.queryByText(/You will ship LLM features/)).not.toBeInTheDocument(); // list only

  await user.click(within(list).getByRole("button", { name: /AI Engineer/ }));
  expect(screen.getByText(/You will ship LLM features/)).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Search results" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Role or keyword")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Back to results/ }));
  expect(await screen.findByRole("list", { name: "Search results" })).toBeInTheDocument();
  expect(screen.getByLabelText("Role or keyword")).toHaveValue("AI Engineer");
  expect(screen.getByLabelText("City or remote")).toHaveValue("Berlin");
  expect(api.calls("/v1/jobs/search")).toHaveLength(1);
});

test("mobile: tailoring from the detail view returns to the same job after the CV is confirmed", async () => {
  setMobile(true);
  const user = userEvent.setup();
  renderApp("/");
  await search(user);
  await user.click(within(await screen.findByRole("list", { name: "Search results" })).getByRole("button", { name: /ML Engineer/ }));
  await user.click(screen.getByRole("button", { name: "Tailor my CV" }));
  await uploadAndConfirm(user);

  expect(await screen.findByText("✓ CV ready for this job")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "ML Engineer" })).toBeInTheDocument();
  expect(api.body("/v1/cv/tailor").job_title).toBe("ML Engineer");
});

test("replacing the CV discards CVs tailored from the old one", async () => {
  const user = userEvent.setup();
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));
  await screen.findByText("✓ CV ready for this job");

  await user.click(screen.getByRole("link", { name: "Review CV" }));
  await user.click(screen.getByRole("button", { name: "Upload a different CV" }));
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "new.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await user.click(await screen.findByRole("button", { name: "Confirm CV" }));

  expect(await screen.findByRole("button", { name: "Tailor my CV" })).toBeInTheDocument();
  expect(screen.queryByText("✓ CV ready for this job")).not.toBeInTheDocument();
});

test("upload errors and empty extraction guide the user", async () => {
  const user = userEvent.setup({ applyAccept: false });
  renderApp("/cv");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "cv.png", { type: "image/png" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unsupported file type");
  expect(api.fetchMock).not.toHaveBeenCalled();

  api.once("/v1/cv/extract-text", () => json({ filename: "scan.pdf", text: "" }));
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "scan.pdf", { type: "application/pdf" }));
  expect(await screen.findByText(/No text could be extracted/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analyze my CV" })).toBeDisabled();
});

test("analysis failure keeps the reviewed text", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/parse", () => json({ detail: "CV coach is unavailable." }, 503));
  renderApp("/cv");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("CV coach is unavailable.");
  expect(screen.getByLabelText("CV text")).toHaveValue("Kerem Aydın\nBackend developer");
});

test("after tailoring, the changes are listed and highlighted in the preview", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/tailor", () => json({
    cv: { ...MY_CV, summary: "Tailored for AI Engineer." },
    warnings: ["Bullet 1 at Test A.Ş.: rewrite reverted (new numbers 40)"],
    changes: [
      { kind: "moved", id: "exp1.b1", where: "Developer — Test A.Ş.", before: "", after: "Built a billing API.", detail: "Moved from 3rd to 1st" },
      { kind: "summary", id: "summary", where: "Summary", before: MY_CV.summary, after: "Tailored for AI Engineer.", detail: "" },
    ],
  }));
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));

  const changes = await screen.findByText(/What changed \(2 changes\)/);
  const list = changes.closest("details")!;
  expect(within(list).getByText("Moved from 3rd to 1st")).toBeInTheDocument();
  expect(within(list).getByText(MY_CV.summary, { exact: false })).toBeInTheDocument(); // before
  expect(within(list).getByText("Tailored for AI Engineer.", { exact: false })).toBeInTheDocument(); // now
  expect(screen.getByText(/never changed/)).toBeInTheDocument();
  expect(screen.getByText(/rewrite reverted/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).toHaveClass("is-changed");
  expect(screen.getByText("Built a billing API.", { exact: false, selector: "li" })).toHaveClass("is-changed");
  expect(screen.getByText(/Highlighted lines changed/)).toBeInTheDocument();
});

test("when nothing changed, the user is told so and nothing is highlighted", async () => {
  const user = userEvent.setup();
  api.once("/v1/cv/tailor", () => json({ cv: MY_CV, warnings: [], changes: [] }));
  renderApp("/cv");
  await uploadAndConfirm(user);
  await search(user);
  await user.click(await screen.findByRole("button", { name: "Tailor my CV" }));

  expect(await screen.findByText(/Nothing needed to change for this job/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Preview CV" }));
  expect(screen.getByTestId("cv-summary")).not.toHaveClass("is-changed");
  expect(screen.queryByText(/Highlighted lines changed/)).not.toBeInTheDocument();
});
