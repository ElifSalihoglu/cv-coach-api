import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MY_CV, fakeApi, json, renderApp, submitPosting } from "./test-utils";

let api: ReturnType<typeof fakeApi>;
type User = ReturnType<typeof userEvent.setup>;

beforeEach(() => {
  api = fakeApi();
  vi.stubGlobal("fetch", api.fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const WARNINGS = [
  "exp1: employer is empty; please fill it in.",
  "exp1.b1 (under Test A.Ş.): bullet text differs from the CV text.",
  "email: 'kerem@example.com' was not found in the CV text.",
  "skill/language: 'Go' was not found in the CV text.",
];

async function toReviewScreen(user: User, warnings: string[] = WARNINGS) {
  api.once("/v1/cv/parse", () => json({ cv: MY_CV, warnings }));
  renderApp("/");
  await user.upload(screen.getByLabelText(/Upload your CV/), new File(["x"], "my-cv.txt", { type: "text/plain" }));
  await user.click(await screen.findByRole("button", { name: "Analyze my CV" }));
  await screen.findByRole("heading", { name: "Confirm your CV" });
}

const section = (name: string) => screen.getByRole("region", { name });

test("each warning is readable and sits next to the part of the CV it is about", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user);

  expect(within(section("Experience")).getByText("⚠ Company is empty; please fill it in.")).toBeInTheDocument();
  expect(within(section("Experience")).getByText("⚠ Bullet 1: bullet text differs from the CV text.")).toBeInTheDocument();
  expect(within(section("Contact")).getByText(/Email: 'kerem@example.com' was not found/)).toBeInTheDocument();
  expect(within(section("Skills and languages")).getByText(/Skill or language: 'Go'/)).toBeInTheDocument();
  expect(within(section("Summary")).queryByText(/⚠/)).not.toBeInTheDocument();
  expect(screen.queryByText(/\bexp1\b/)).not.toBeInTheDocument();
});

test("editing a section: confirm is blocked meanwhile, saving keeps the edit and clears that section's warnings", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user);

  await user.click(screen.getByRole("button", { name: "Edit Experience" }));
  expect(screen.getByRole("button", { name: "Confirm CV" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Edit Contact" })).toBeDisabled(); // one section at a time
  expect(screen.getByText("Save or cancel the section you are editing first.")).toBeInTheDocument();

  const form = within(section("Experience"));
  await user.clear(form.getByLabelText("Company"));
  await user.type(form.getByLabelText("Company"), "Test Corp");
  await user.clear(form.getByLabelText("Bullet 1"));
  await user.type(form.getByLabelText("Bullet 1"), "Built and ran a billing API.");
  await user.click(form.getByRole("button", { name: "Add bullet" }));
  await user.type(form.getByLabelText("Bullet 2"), "Led the on-call rotation.");
  await user.click(form.getByRole("button", { name: "Save" }));

  const view = within(section("Experience"));
  expect(view.getByText("Developer — Test Corp")).toBeInTheDocument();
  expect(view.getByText("Built and ran a billing API.")).toBeInTheDocument();
  expect(view.getByText("Led the on-call rotation.")).toBeInTheDocument();
  expect(view.queryByText(/⚠/)).not.toBeInTheDocument(); // reviewed: warnings gone
  expect(within(section("Contact")).getByText(/⚠/)).toBeInTheDocument(); // other sections keep theirs
  expect(screen.getByRole("button", { name: "Confirm CV" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Discard edits and go back" })).toBeInTheDocument();
});

test("cancel throws the edit away", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user, []);

  await user.click(screen.getByRole("button", { name: "Edit Summary" }));
  const box = within(section("Summary")).getByLabelText("Summary");
  await user.clear(box);
  await user.type(box, "Something else entirely.");
  await user.click(within(section("Summary")).getByRole("button", { name: "Cancel" }));

  expect(within(section("Summary")).getByText(MY_CV.summary)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Back to text" })).toBeInTheDocument(); // nothing was edited
});

test("contact, skills and languages are edited as comma separated lists", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user, []);

  await user.click(screen.getByRole("button", { name: "Edit Contact" }));
  const contact = within(section("Contact"));
  await user.clear(contact.getByLabelText("Name"));
  await user.type(contact.getByLabelText("Name"), "Kerem A. Aydın");
  await user.type(contact.getByLabelText("Links (comma separated)"), "github.com/kerem, kerem.dev");
  await user.click(contact.getByRole("button", { name: "Save" }));
  expect(within(section("Contact")).getByText("Kerem A. Aydın")).toBeInTheDocument();
  expect(within(section("Contact")).getByText(/github.com\/kerem \| kerem.dev/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Edit Skills and languages" }));
  const skills = within(section("Skills and languages"));
  await user.clear(skills.getByLabelText("Skills (comma separated)"));
  await user.type(skills.getByLabelText("Skills (comma separated)"), "Python, , SQL ,Go");
  await user.type(skills.getByLabelText("Languages (comma separated)"), "Turkish, English");
  await user.click(skills.getByRole("button", { name: "Save" }));
  expect(within(section("Skills and languages")).getByText(/Python, SQL, Go/)).toBeInTheDocument();
  expect(within(section("Skills and languages")).getByText(/Turkish, English/)).toBeInTheDocument();
});

test("the confirmed CV is the edited one: the analysis uses it, and editing never calls a model", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user);

  await user.click(screen.getByRole("button", { name: "Edit Experience" }));
  const form = within(section("Experience"));
  await user.clear(form.getByLabelText("Company"));
  await user.type(form.getByLabelText("Company"), "Test Corp");
  await user.click(form.getByRole("button", { name: "Add bullet" }));
  await user.type(form.getByLabelText("Bullet 2"), "Led the on-call rotation.");
  await user.click(form.getByRole("button", { name: "Save" }));
  await user.click(screen.getByRole("button", { name: "Confirm CV" }));

  await submitPosting(user);
  await screen.findByRole("heading", { name: "Suggestions for this application" });

  const sent = api.body("/v1/coach/analyze").cv;
  expect(sent.experiences[0].employer).toBe("Test Corp");
  expect(sent.experiences[0].bullets.map((b: { id: string }) => b.id)).toEqual(["exp1.b1", "exp1.b2"]);
  expect(sent.experiences[0].bullets[1].text).toBe("Led the on-call rotation.");
  expect(api.calls("/v1/cv/parse")).toHaveLength(1); // edits made no model call
  expect(api.calls("/v1/cv/extract-text")).toHaveLength(1);
});

test("removing a bullet drops it; blank bullets are dropped on save", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user, []);

  await user.click(screen.getByRole("button", { name: "Edit Experience" }));
  const form = within(section("Experience"));
  await user.click(form.getByRole("button", { name: "Add bullet" })); // left blank
  await user.click(form.getByRole("button", { name: "Remove bullet 1" }));
  await user.click(form.getByRole("button", { name: "Save" }));

  expect(within(section("Experience")).queryByText("Built a billing API.")).not.toBeInTheDocument();
  expect(within(section("Experience")).queryAllByRole("listitem")).toHaveLength(0);
});

test("going back to the text discards the edits and re-analysing starts from a fresh result", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user, []);
  await user.click(screen.getByRole("button", { name: "Edit Summary" }));
  await user.type(within(section("Summary")).getByLabelText("Summary"), " More.");
  await user.click(within(section("Summary")).getByRole("button", { name: "Save" }));

  await user.click(screen.getByRole("button", { name: "Discard edits and go back" }));
  expect(screen.getByLabelText("CV text")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Analyze my CV" }));
  expect(await within(await screen.findByRole("region", { name: "Summary" })).findByText(MY_CV.summary)).toBeInTheDocument();
});

test("sections without items have no Edit button", async () => {
  const user = userEvent.setup();
  await toReviewScreen(user, []);
  expect(screen.queryByRole("button", { name: "Edit Projects" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit Education" })).not.toBeInTheDocument();
  expect(within(section("Projects")).getByText("Nothing found.")).toBeInTheDocument();
});
