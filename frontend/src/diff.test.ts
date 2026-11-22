import { expect, test } from "vitest";
import { diffWords } from "./diff";

const marked = (pieces: { text: string; changed: boolean }[]) =>
  pieces.filter((p) => p.changed).map((p) => p.text);

test("texts that differ only in spacing have nothing marked", () => {
  const nbsp = String.fromCharCode(0xa0);
  const d = diffWords(`Built a billing API for${nbsp}200 merchants\nusing  Python. `, "Built a billing API for 200 merchants using Python.");
  expect(marked(d.before)).toEqual([]);
  expect(marked(d.after)).toEqual([]);
});

test("a changed number is the only thing marked", () => {
  const d = diffWords("Reduced backlog by 3 years of data.", "Reduced backlog by 5 years of data.");
  expect(marked(d.before)).toEqual(["3"]);
  expect(marked(d.after)).toEqual(["5"]);
});

test("added and removed words are marked on their own side", () => {
  const d = diffWords("Built an API quickly", "Built an API for billing");
  expect(marked(d.before)).toEqual(["quickly"]);
  expect(marked(d.after)).toEqual(["for", "billing"]);
});

test("case counts as a change", () => {
  expect(marked(diffWords("Led the team", "led the team").after)).toEqual(["led"]);
});
