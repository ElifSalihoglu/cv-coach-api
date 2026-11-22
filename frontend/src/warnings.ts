/**
 * Parse warnings come from the API with technical ids ("exp1 employer: ...").
 * This turns them into readable text and says which section and item of the
 * review screen each one belongs to, so it can be shown right next to that item.
 */
export type SectionKey =
  | "contact" | "summary" | "experience" | "projects" | "education"
  | "certifications" | "skills";

export interface RoutedWarning {
  section: SectionKey | "general";
  /** exp1, edu1, ... or null for a whole section. */
  itemId: string | null;
  text: string;
}

const FIELD_LABELS: Record<string, string> = {
  name: "Name", email: "Email", phone: "Phone", location: "Location",
  summary: "Summary", employer: "Company", title: "Title",
  start: "Start date", end: "End date", school: "School",
  degree: "Degree", details: "Details", description: "Description",
  issuer: "Issuer", date: "Date",
};

const SECTION_BY_PREFIX: Record<string, SectionKey> = {
  exp: "experience", edu: "education", proj: "projects", cert: "certifications",
};

const ITEM =
  /^(?<id>(?<prefix>exp|edu|proj|cert)\d+)(?:\.b(?<bullet>\d+))?(?:\s*\([^)]*\))?(?:\s+(?<field>[a-z]+))?\s*:\s*(?<rest>.*)$/;
const TOP_LEVEL = /^(?<field>name|email|phone|location|summary)\s*:\s*(?<rest>.*)$/;

export function routeWarning(warning: string): RoutedWarning {
  const item = ITEM.exec(warning);
  if (item?.groups) {
    const { id, prefix, bullet, field, rest } = item.groups;
    let text: string;
    if (bullet) {
      text = `Bullet ${bullet}: ${rest}`;
    } else if (field && field in FIELD_LABELS) {
      text = `${FIELD_LABELS[field]}: ${rest}`;
    } else {
      // "exp1: employer is empty; please fill it in."
      const space = rest.indexOf(" ");
      const first = space === -1 ? rest : rest.slice(0, space);
      const tail = space === -1 ? "" : rest.slice(space + 1);
      text = first in FIELD_LABELS ? `${FIELD_LABELS[first]} ${tail}`.trim() : rest;
    }
    return { section: SECTION_BY_PREFIX[prefix], itemId: id, text };
  }

  const top = TOP_LEVEL.exec(warning);
  if (top?.groups) {
    const { field, rest } = top.groups;
    return {
      section: field === "summary" ? "summary" : "contact",
      itemId: null,
      text: `${FIELD_LABELS[field]}: ${rest}`,
    };
  }

  if (warning.startsWith("skill/language")) {
    const rest = warning.includes(":") ? warning.slice(warning.indexOf(":") + 1).trim() : warning;
    return { section: "skills", itemId: null, text: `Skill or language: ${rest}` };
  }
  return { section: "general", itemId: null, text: warning };
}
