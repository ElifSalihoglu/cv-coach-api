import { diffWords } from "../diff";
import type { CvChange } from "../types";
import { Words } from "./Words";

const LABELS: Record<CvChange["kind"], string> = {
  summary: "Summary rewritten",
  moved: "Moved up",
  rewritten: "Reworded",
  moved_rewritten: "Reworded and moved",
  added: "Added by you",
};

/** One role (or the summary) and the changes inside it. The id, not the label, tells roles apart. */
interface Group { key: string; where: string; changes: CvChange[] }

function groupChanges(changes: CvChange[]): Group[] {
  const groups = new Map<string, Group>();
  for (const c of changes) {
    const key = c.id === "summary" ? "summary" : c.id.split(".b")[0];
    if (!groups.has(key)) groups.set(key, { key, where: c.where, changes: [] });
    groups.get(key)!.changes.push(c);
  }
  return [...groups.values()];
}

function counts(changes: CvChange[]): string {
  const n = (test: (c: CvChange) => boolean) => changes.filter(test).length;
  return [
    [n((c) => c.kind === "summary"), "summary"],
    [n((c) => c.kind === "moved" || c.kind === "moved_rewritten"), "moved"],
    [n((c) => c.kind === "rewritten" || c.kind === "moved_rewritten"), "reworded"],
    [n((c) => c.kind === "added"), "added"],
  ]
    .filter(([count]) => count !== 0)
    .map(([count, label]) => `${count} ${label}`)
    .join(" · ");
}

/**
 * What differs from the confirmed CV. Short by default (just the count); the
 * details open on request, with the changed words highlighted.
 */
export function ChangesList({ changes }: { changes: CvChange[] }) {
  if (changes.length === 0) {
    return (
      <p className="changes-none">
        Nothing needed to change for this job. This CV is the same as your confirmed CV.
      </p>
    );
  }
  const noun = changes.length === 1 ? "change" : "changes";
  return (
    <details className="changes">
      <summary>
        What changed ({changes.length} {noun})
        <span className="changes-counts">{counts(changes)}</span>
      </summary>
      <p className="hint">Your name, contacts, jobs, dates and skills are never changed.</p>
      {groupChanges(changes).map((group) => (
        <section key={group.key} className="change-group" aria-label={group.where}>
          <h4>{group.where}</h4>
          <ul>
            {group.changes.map((c) => {
              const diff = c.before ? diffWords(c.before, c.after) : null;
              return (
                <li key={`${c.kind}:${c.id}`} className={`change change-${c.kind}`}>
                  <p className="change-kind">
                    {LABELS[c.kind]}
                    {c.detail && <span className="change-detail"> · {c.detail}</span>}
                    {c.user_added && c.kind !== "added" && (
                      <span className="change-detail"> · Includes details you confirmed</span>
                    )}
                  </p>
                  {diff ? (
                    <>
                      <p className="change-before"><span className="tag">Before</span> <Words pieces={diff.before} /></p>
                      <p className="change-after"><span className="tag">Now</span> <Words pieces={diff.after} /></p>
                    </>
                  ) : (
                    <p className="change-after">{c.after}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </details>
  );
}
