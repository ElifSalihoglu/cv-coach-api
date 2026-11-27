import { useState } from "react";
import { checkText, errorMessage } from "../api";
import type { DraftAction } from "../analysisStore";
import type { Addition, Claim, Question, StructuredCV } from "../types";

interface Props {
  question: Question;
  addition: Addition | undefined;
  declined: boolean;
  jobDescription: string;
  mainCv: StructuredCV;
  onAction: (action: DraftAction) => void;
}

type Mode = "idle" | "answering" | "confirm";

/** Where a new line could go: one of the user's roles or projects. */
function places(cv: StructuredCV) {
  return [
    ...cv.experiences.map((e) => ({
      value: `experience:${e.id}`,
      label: [e.title, e.employer].filter(Boolean).join(" — ") || e.id,
    })),
    ...cv.projects.map((p) => ({ value: `project:${p.id}`, label: `Project: ${p.name || p.id}` })),
  ];
}

/**
 * A question about something the posting asks for and the CV does not mention.
 * Nothing is added until the user answers; the answer is their own wording, and the
 * user says which role or project it belongs to.
 */
export function QuestionCard({ question: q, addition, declined, jobDescription, mainCv, onAction }: Props) {
  const options = places(mainCv);
  const [mode, setMode] = useState<Mode>("idle");
  const [text, setText] = useState("");
  const [place, setPlace] = useState(options[0]?.value ?? "");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [sure, setSure] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function add(confirmed: string[]) {
    const [type, id] = place.split(":");
    onAction({
      type: "answer", id: q.id, target: { type: type as "experience" | "project", id },
      text: text.trim(), confirmed,
    });
    setMode("idle");
  }

  async function review() {
    setProblem(null);
    setBusy(true);
    try {
      const result = await checkText({ cv: mainCv, job_description: jobDescription, kind: "add", text });
      if (result.claims.length === 0) {
        add([]);
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

  const where = addition ? options.find((o) => o.value === `${addition.target.type}:${addition.target.id}`)?.label : "";
  return (
    <article className="suggestion question" aria-label={`Question about ${q.term}`}>
      <header className="suggestion-head">
        <span className="suggestion-kind">Question</span>
        <span className={`level level-${q.level}`}>{q.level === "required" ? "Required" : "Preferred"}</span>
      </header>
      <p className="suggestion-line"><span className="tag">Posting</span> “{q.requirement}”</p>
      <p>{q.text}</p>

      {!addition && !declined && mode === "idle" && (
        <div className="button-row">
          <button type="button" onClick={() => setMode("answering")}>Yes, I used it…</button>
          <button type="button" onClick={() => onAction({ type: "decline", id: q.id })}>No</button>
        </div>
      )}

      {mode === "answering" && (
        <div className="suggestion-edit">
          <label className="field">
            <span>What did you do with {q.term}?</span>
            <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <label className="field">
            <span>Where did you use it?</span>
            <select value={place} onChange={(e) => setPlace(e.target.value)}>
              {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          {problem && <p className="error" role="alert">{problem}</p>}
          <div className="button-row">
            <button type="button" className="primary" disabled={busy || !text.trim() || !place} onClick={review}>
              {busy ? "Checking…" : "Review"}
            </button>
            <button type="button" onClick={() => setMode("idle")}>Cancel</button>
          </div>
        </div>
      )}

      {mode === "confirm" && (
        <div className="suggestion-confirm" role="group" aria-label="Confirm new claims">
          <p><strong>This adds something your CV does not say yet:</strong> <mark>{claims.flatMap((c) => c.terms).join(", ")}</mark></p>
          <label className="check">
            <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            I confirm this is true about my experience
          </label>
          <div className="button-row">
            <button type="button" className="primary" disabled={!sure}
                    onClick={() => add(claims.flatMap((c) => c.terms))}>
              Add to my CV
            </button>
            <button type="button" onClick={() => setMode("answering")}>Back</button>
          </div>
        </div>
      )}

      {addition && (
        <div className="decision">
          <span className="status-ready">✓ Added to {where}: “{addition.text}”</span>
          <button type="button" className="link-button" onClick={() => onAction({ type: "undo", id: q.id })}>Undo</button>
        </div>
      )}
      {declined && (
        <div className="decision">
          <span className="muted">Noted: nothing added</span>
          <button type="button" className="link-button" onClick={() => onAction({ type: "undo", id: q.id })}>Undo</button>
        </div>
      )}
    </article>
  );
}
