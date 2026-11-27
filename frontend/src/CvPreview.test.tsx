import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { CvPreview } from "./components/CvPreview";
import { RICH_CV } from "./test-utils";
import type { StructuredCV } from "./types";

// The PDF renders the same sections in the same order; tests/test_cv_parse_and_render.py checks its side.
const SECTION_ORDER = ["Summary", "Experience", "Projects", "Education", "Certifications", "Skills", "Languages"];

const FULL_CV: StructuredCV = {
  ...RICH_CV,
  links: ["github.com/kerem"],
  phone: "+90 555 000 00 00",
  projects: [{ id: "proj1", name: "Data quality panel", description: "Reports schema changes." }],
  education: [{ id: "edu1", school: "Test University", degree: "B.Sc. Computer Engineering", start: "2014", end: "2018", details: "Thesis on anomaly detection." }],
  certifications: [{ id: "cert1", name: "Cloud Practitioner", issuer: "Example Academy", date: "2022" }],
  languages: ["Turkish (native)", "English (C1)"],
};

test("the preview shows the sections in the order the PDF prints them", () => {
  render(<CvPreview cv={FULL_CV} />);
  const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(headings).toEqual(SECTION_ORDER);
});

test("empty sections are left out, as in the PDF", () => {
  render(<CvPreview cv={{ ...RICH_CV, summary: "", skills: [] }} />);
  const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(headings).toEqual(["Experience"]);
});

test("the contact line and the dated lines are joined the way the PDF joins them", () => {
  render(<CvPreview cv={FULL_CV} />);
  expect(screen.getByText("kerem@example.com | +90 555 000 00 00 | Ankara | github.com/kerem")).toBeInTheDocument();
  expect(screen.getByText("Developer — Test A.Ş.")).toBeInTheDocument();
  expect(screen.getByText("2020 – 2024")).toBeInTheDocument();
  expect(screen.getByText("B.Sc. Computer Engineering — Test University")).toBeInTheDocument();
  expect(screen.getByText("Cloud Practitioner — Example Academy — 2022")).toBeInTheDocument();
});
