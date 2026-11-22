import type { CvChange } from "../types";

/** What differs from the confirmed CV, in plain words. Only real differences are listed. */
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
    <details className="changes" open>
      <summary>What changed ({changes.length} {noun})</summary>
      <p className="hint">Your name, contacts, jobs, dates and skills are never changed.</p>
      <ul>
        {changes.map((c) => (
          <li key={`${c.kind}:${c.id}`} className={`change change-${c.kind}`}>
            <p className="change-where">
              {c.kind === "summary" ? "Summary rewritten" : c.kind === "rewritten" ? "Reworded" : "Moved up"}
              {c.kind !== "summary" && <> · {c.where}</>}
            </p>
            {c.kind === "moved" && (
              <>
                <p className="change-detail">{c.detail}</p>
                <p className="change-after">{c.after}</p>
              </>
            )}
            {c.kind !== "moved" && (
              <>
                {c.before && (
                  <p className="change-before"><span className="tag">Before</span> {c.before}</p>
                )}
                <p className="change-after"><span className="tag">Now</span> {c.after}</p>
              </>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
