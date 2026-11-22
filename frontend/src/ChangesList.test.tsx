import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { ChangesList } from "./components/ChangesList";
import type { CvChange } from "./types";

const NBSP = String.fromCharCode(0xa0);

const change = (over: Partial<CvChange>): CvChange => ({
  kind: "rewritten", id: "exp1.b1", where: "Engineer — Acme", before: "", after: "", detail: "", ...over,
});

const CHANGES: CvChange[] = [
  change({ kind: "moved_rewritten", id: "exp1.b3", detail: "Moved from 3rd to 1st",
           before: `Reduced backlog by 3${NBSP}years\nof data.`, after: "Reduced backlog by 5 years of data." }),
  change({ kind: "moved", id: "exp2.b2", where: "Engineer — Beta", after: "Mentored four engineers.", detail: "Moved from 2nd to 1st" }),
  change({ kind: "summary", id: "summary", where: "Summary", before: "Old summary.", after: "New summary." }),
  change({ kind: "rewritten", id: "exp1.b1", before: "Alpha beta.", after: "Alpha gamma." }),
];

test("short by default: only the number of changes and a breakdown; details open on request", async () => {
  const user = userEvent.setup();
  render(<ChangesList changes={CHANGES} />);

  const summary = screen.getByText(/What changed \(4 changes\)/);
  const panel = summary.closest("details")!;
  expect(panel).not.toHaveAttribute("open");
  expect(within(summary).getByText("1 summary · 2 moved · 2 reworded")).toBeInTheDocument();

  await user.click(summary);
  expect(panel).toHaveAttribute("open");
});

test("a bullet that was moved and reworded is one entry, not two", () => {
  const { container } = render(<ChangesList changes={CHANGES} />);
  expect(screen.getAllByText("Reworded and moved")).toHaveLength(1);
  expect(container.querySelectorAll("li")).toHaveLength(4); // one per change, none repeated
  const entry = container.querySelector(".change-moved_rewritten")!;
  expect(entry).toHaveTextContent("Moved from 3rd to 1st");
  expect(entry.querySelector(".change-before")).toHaveTextContent("Reduced backlog by 3 years of data.");
  expect(entry.querySelector(".change-after")).toHaveTextContent("Reduced backlog by 5 years of data.");
  expect(screen.getByText("Moved up", { selector: ".change-kind" })).toBeInTheDocument(); // the pure move
});

test("only the changed words are highlighted in Before and Now", () => {
  const { container } = render(<ChangesList changes={CHANGES} />);
  const first = container.querySelector(".change-moved_rewritten")!;
  expect([...first.querySelectorAll(".change-before mark")].map((m) => m.textContent)).toEqual(["3"]);
  expect([...first.querySelectorAll(".change-after mark")].map((m) => m.textContent)).toEqual(["5"]);
});

test("changes are grouped by role even when two roles look alike", () => {
  render(<ChangesList changes={[
    change({ kind: "moved", id: "exp1.b2", where: "Engineer — Acme (2018 – 2020)", after: "One.", detail: "Moved from 2nd to 1st" }),
    change({ kind: "moved", id: "exp2.b2", where: "Engineer — Acme (2020 – 2022)", after: "Two.", detail: "Moved from 2nd to 1st" }),
  ]} />);
  const groups = screen.getAllByRole("region");
  expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual([
    "Engineer — Acme (2018 – 2020)", "Engineer — Acme (2020 – 2022)",
  ]);
  expect(within(groups[0]).getByText("One.")).toBeInTheDocument();
  expect(within(groups[1]).getByText("Two.")).toBeInTheDocument();
});

test("no changes: says so instead of an empty panel", () => {
  render(<ChangesList changes={[]} />);
  expect(screen.getByText(/Nothing needed to change/)).toBeInTheDocument();
  expect(screen.queryByText(/What changed/)).not.toBeInTheDocument();
});
