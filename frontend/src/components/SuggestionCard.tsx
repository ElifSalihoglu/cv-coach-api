import { useState } from "react";
import { checkText, errorMessage } from "../api";
import type { DraftAction } from "../coachStore";
import { diffWords } from "../diff";
import type { Claim, Decision, FoundJob, StructuredCV, Suggestion } from "../types";
import { Words } from "./Words";

const KIND_LABEL: Record<Suggestion["kind"], string> = {
  promote: "Move up",
  rewrite: "Reword",
  summary: "Rewrite summary",
};

interface Props {
  suggestion: Suggestion;
  decision: Decision | undefined;
  rejected: boolean;
  job: FoundJob;
  mainCv: StructuredCV;
  onAction: (action: DraftAction) => void;
}

type Mode = "idle" | "editing" | "confirm";

/** One proposal with the evidence behind it, and the user's three choices. */
export function SuggestionCard({ suggestion: s, decision, rejected, job, mainCv, onAction }: Props) {
  const [mode, setMode] = useState<Mode>("idle");
  const [text, setText] = useState(s.after);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [sure, setSure] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const source = s.sources[0];
  const decided = decision !== undefined;
  const state = decision?.action === "edit" ? "edited" : decision ? "accepted" : rejected ? "rejected" : "open";

  async function checkAndAccept() {
    setProblem(null);
    setBusy(true);
    try {
      const result = await checkText({
        cv: mainCv, job_description: job.job_description,
        kind: s.kind === "rewrite" ? "rewrite" : "summary",
        source_id: s.kind === "rewrite" ? source.id : undefined, text,
      });
      if (result.claims.length === 0) {
        onAction({ type: "edit", id: s.id, text: text.trim(), confirmed: [] });
        setMode("idle");
      } else {
        setClaims(result.claims);
        setSure(false);
        setMode("confirm");
      }
    } catch (err) {
      setProblem(errorMessage(err, "Could not check your text."));
    } finally {
      setBusy(false);
    }
  }

  function acceptWithClaims() {
    onAction({ type: "edit", id: s.id, text: text.trim(), confirmed: claims.flatMap((c) => c.terms) });
    setMode("idle");
  }

  return (
    <article className={`suggestion is-${state}`} aria-label={`${KIND_LABEL[s.kind]} suggestion`}>
      <header className="suggestion-head">
        <span className="suggestion-kind">{KIND_LABEL[s.kind]}</span>
        <span className={`level level-${s.level}`}>{s.level === "required" ? "Required" : "Preferred"}</span>
        {s.support === "related" && <span className="related">Related experience</span>}
      </header>

      <p className="suggestion-line"><span className="tag">Posting</span> “{s.requirement}”</p>
      {s.sources.map((src) => (
        <p className="suggestion-line" key={src.id}>
          <span className="tag">Your CV</span> {src.where}: “{src.text}”
        </p>
      ))}

      {s.kind === "promote" ? (
        <p className="suggestion-change">
          Now line {s.position} in this role. Suggested: line 1.
        </p>
      ) : (
        <SuggestionDiff before={s.before} after={s.after} />
      )}
      <p className="suggestion-why">{s.rationale}</p>

      {mode === "idle" && state === "open" && (
        <div className="button-row">
          <button type="button" className="primary" onClick={() => onAction({ type: "accept", id: s.id })}>Accept</button>
          {s.kind !== "promote" && (
            <button type="button" onClick={() => { setText(s.after); setMode("editing"); }}>Edit &amp; accept</button>
          )}
          <button type="button" onClick={() => onAction({ type: "reject", id: s.id })}>Reject</button>
        </div>
      )}

      {mode === "editing" && (
        <div className="suggestion-edit">
          <label className="field">
            <span>Your wording</span>
            <textarea rows={s.kind === "summary" ? 4 : 3} value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          {problem && <p className="error" role="alert">{problem}</p>}
          <div className="button-row">
            <button type="button" className="primary" disabled={busy || !text.trim()} onClick={checkAndAccept}>
              {busy ? "Checking…" : "Accept my wording"}
            </button>
            <button type="button" onClick={() => setMode("idle")}>Cancel</button>
          </div>
        </div>
      )}

      {mode === "confirm" && (
        <div className="suggestion-confirm" role="group" aria-label="Confirm new claims">
          <p><strong>Your text says something your CV does not.</strong></p>
          <ul>
            {claims.map((c) => (
              <li key={c.kind}>
                {c.kind === "skills" ? "Not in your CV" : c.kind === "numbers" ? "Number not in your CV" : "Claim not in your CV"}:{" "}
                <mark>{c.terms.join(", ")}</mark>
              </li>
            ))}
          </ul>
          <p className="suggestion-line">
            <span className="tag">Difference</span>{" "}
            <Words pieces={diffWords(s.before, text).after} />
          </p>
          <label className="check">
            <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            I confirm this is true about my experience
          </label>
          <div className="button-row">
            <button type="button" className="primary" disabled={!sure} onClick={acceptWithClaims}>Add to my CV</button>
            <button type="button" onClick={() => setMode("editing")}>Back to editing</button>
          </div>
        </div>
      )}

      {decided && (
        <div className="decision">
          <span className="status-ready">
            {state === "edited" ? "✓ Accepted with your wording" : "✓ Accepted"}
          </span>
          <button type="button" className="link-button" onClick={() => onAction({ type: "undo", id: s.id })}>Undo</button>
        </div>
      )}
      {state === "rejected" && (
        <div className="decision">
          <span className="muted">Rejected</span>
          <button type="button" className="link-button" onClick={() => onAction({ type: "undo", id: s.id })}>Undo</button>
        </div>
      )}
    </article>
  );
}

function SuggestionDiff({ before, after }: { before: string; after: string }) {
  const diff = diffWords(before, after);
  return (
    <>
      <p className="change-before"><span className="tag">Now</span> <Words pieces={diff.before} /></p>
      <p className="change-after"><span className="tag">Suggested</span> <Words pieces={diff.after} /></p>
    </>
  );
}
