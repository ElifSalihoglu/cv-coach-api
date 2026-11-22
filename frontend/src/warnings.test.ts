import { expect, test } from "vitest";
import { routeWarning } from "./warnings";

test("parse warnings route to their section and lose the technical ids", () => {
  const cases: Record<string, [string, string | null, string]> = {
    "exp1 employer: 'Acme' was not found in the CV text.":
      ["experience", "exp1", "Company: 'Acme' was not found in the CV text."],
    "exp2: employer is empty; please fill it in.":
      ["experience", "exp2", "Company is empty; please fill it in."],
    "exp1.b2 (under Acme): bullet text differs from the CV text.":
      ["experience", "exp1", "Bullet 2: bullet text differs from the CV text."],
    "edu1: school and degree are both empty.":
      ["education", "edu1", "School and degree are both empty."],
    "proj1: name is empty; please fill it in.":
      ["projects", "proj1", "Name is empty; please fill it in."],
    "cert1 issuer: 'X' was not found in the CV text.":
      ["certifications", "cert1", "Issuer: 'X' was not found in the CV text."],
    "email: 'a@b.c' was not found in the CV text.":
      ["contact", null, "Email: 'a@b.c' was not found in the CV text."],
    "summary: 'x' was not found in the CV text.":
      ["summary", null, "Summary: 'x' was not found in the CV text."],
    "skill/language: 'Go' was not found in the CV text.":
      ["skills", null, "Skill or language: 'Go' was not found in the CV text."],
    "something unexpected": ["general", null, "something unexpected"],
  };
  for (const [raw, [section, itemId, text]] of Object.entries(cases)) {
    expect(routeWarning(raw), raw).toEqual({ section, itemId, text });
  }
});

test("no routed warning shows an experience id to the user", () => {
  for (const raw of [
    "exp1 title: 'Dev' was not found in the CV text.",
    "exp3: start is empty; please fill it in.",
    "edu2 details: 'x' was not found in the CV text.",
  ]) {
    expect(routeWarning(raw).text).not.toMatch(/\b(exp|edu|proj|cert)\d/);
  }
});
