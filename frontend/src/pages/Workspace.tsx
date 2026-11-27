import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, parseCv } from "../api";
import { AnalysisView } from "../components/AnalysisView";
import { CvPreview } from "../components/CvPreview";
import { CvReview } from "../components/CvReview";
import { PostingForm } from "../components/PostingForm";
import { UploadCv } from "../components/UploadCv";
import { useSession } from "../session";
import type { SectionKey } from "../warnings";

const STEPS = ["Upload", "Review text", "Confirm CV", "Job posting", "Suggestions"];

function Steps({ current }: { current: number }) {
  return (
    <ol className="steps" aria-label="Progress">
      {STEPS.map((label, i) => (
        <li key={label} aria-current={i + 1 === current ? "step" : undefined}
            className={i + 1 === current ? "is-current" : i + 1 < current ? "is-done" : ""}>
          {i + 1}. {label}
        </li>
      ))}
    </ol>
  );
}

/** The whole flow on one page: the step shown follows how far the user has got. */
export function Workspace() {
  const { cv, analysis } = useSession();
  if (cv.confirmedCv) return analysis.analysis ? <ResultsStep /> : <PostingStep />;
  if (cv.parsed) return <ConfirmStep />;
  if (cv.text !== null) return <TextStep />;
  return <UploadStep />;
}

function UploadStep() {
  const { startCv } = useSession();
  return (
    <section className="step">
      <Steps current={1} />
      <h1>Tailor your CV to a job</h1>
      <p className="lead">
        Upload your CV, paste a job posting, and review suggestions that show what the posting asks for.
        Every suggestion rests on a line of your CV, and nothing changes until you accept it.
      </p>
      <UploadCv onExtracted={startCv} />
      <p className="muted small">
        No CV at hand? <Link to="/demo">Explore the demo</Link> with sample data.
      </p>
    </section>
  );
}

function TextStep() {
  const { cv, setCvText, setParsed, resetCv } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const text = cv.text ?? "";

  async function analyze() {
    setBusy(true);
    setError(null);
    try {
      setParsed(await parseCv(text));
    } catch (err) {
      setError(`Could not analyze your CV. ${errorMessage(err, "")}`.trim());
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="step">
      <Steps current={2} />
      <h1>Review your CV text</h1>
      <p className="muted">
        File: <strong>{cv.fileName}</strong>. This exact text is sent to the language
        model once, to structure your CV. Edit or remove anything you do not want sent.
      </p>
      {!text.trim() && (
        <p className="warning" role="status">
          No text could be extracted from this file (a scanned PDF?). Paste your CV text below to continue.
        </p>
      )}
      <label className="field">
        <span>CV text</span>
        <textarea rows={16} value={text} onChange={(e) => setCvText(e.target.value)} />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions">
        <button type="button" className="primary" onClick={analyze} disabled={busy || !text.trim()}>
          {busy ? "Analyzing your CV…" : "Analyze my CV"}
        </button>
        <button type="button" onClick={resetCv}>Choose a different file</button>
      </div>
    </section>
  );
}

function ConfirmStep() {
  const { cv, setParsed, saveParsedEdit, confirmCv } = useSession();
  const [editing, setEditing] = useState<SectionKey | null>(null);
  const parsed = cv.parsed!;
  return (
    <section className="step">
      <Steps current={3} />
      <h1>Confirm your CV</h1>
      <p className="muted">
        This is how your CV was understood. Every suggestion is built from it.
        Fix anything that is wrong with Edit, then confirm.
      </p>
      <div className="actions">
        <button type="button" className="primary" disabled={editing !== null} onClick={() => confirmCv(parsed.cv)}>
          Confirm CV
        </button>
        <button type="button" disabled={editing !== null} onClick={() => setParsed(null)}>
          {parsed.edited ? "Discard edits and go back" : "Back to text"}
        </button>
        {editing !== null && <span className="muted">Save or cancel the section you are editing first.</span>}
      </div>
      <CvReview
        cv={parsed.cv}
        warnings={parsed.warnings}
        reviewed={parsed.reviewed}
        editing={editing}
        setEditing={setEditing}
        onSave={saveParsedEdit}
      />
    </section>
  );
}

function ConfirmedCv() {
  const { cv, resetCv } = useSession();
  const [open, setOpen] = useState(false);
  return (
    <details className="confirmed-cv" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <span className="ready-mark">✓ CV confirmed</span> · {cv.fileName}
      </summary>
      <div className="actions">
        <button type="button" onClick={resetCv}>Upload a different CV</button>
        <span className="muted small">This discards the suggestions made from the current one.</span>
      </div>
      {open && <CvPreview cv={cv.confirmedCv!} />}
    </details>
  );
}

function PostingStep() {
  const { analysis } = useSession();
  return (
    <section className="step">
      <Steps current={4} />
      <h1>Add the job posting</h1>
      <p className="muted">
        Paste the posting you want to apply to. The suggestions are about this posting only.
      </p>
      <ConfirmedCv />
      <PostingForm onSubmit={(options) => void analysis.start(options)} />
    </section>
  );
}

function ResultsStep() {
  const { cv, analysis: store } = useSession();
  const analysis = store.analysis!;
  return (
    <section className="step wide">
      <Steps current={5} />
      <ConfirmedCv />
      <AnalysisView
        analysis={analysis}
        mainCv={cv.confirmedCv!}
        controls={{
          choose: (focus) => void store.choose(focus),
          changeFocus: store.changeFocus,
          decide: (action) => void store.decide(action),
          retry: () => void store.start(analysis),
          reset: store.reset,
        }}
      />
    </section>
  );
}
