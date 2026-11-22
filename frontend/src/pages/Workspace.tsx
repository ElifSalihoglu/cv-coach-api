import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage, parseCv } from "../api";
import { CvPreview } from "../components/CvPreview";
import { UploadCv } from "../components/UploadCv";
import { useSession } from "../session";

type Stage = 1 | 2 | 3;

/** Where "back to jobs" goes: the job the user was tailoring for, if any. */
function useJobsPath(): string {
  const { session } = useSession();
  return session.pendingTailorJobId ? `/?job=${encodeURIComponent(session.pendingTailorJobId)}` : "/";
}

/** The CV pages: upload, review the text, confirm the structured CV. */
export function Workspace() {
  const { session } = useSession();
  const { text, parsed, confirmedCv } = session.cv;
  if (confirmedCv) return <ConfirmedStep />;
  if (parsed) return <ConfirmStep />;
  if (text !== null) return <TextStep />;
  return <UploadStep />;
}

function Steps({ current }: { current: Stage }) {
  const labels = ["Upload", "Review text", "Confirm CV"];
  return (
    <ol className="steps" aria-label="Progress">
      {labels.map((label, i) => (
        <li key={label} aria-current={i + 1 === current ? "step" : undefined}
            className={i + 1 === current ? "is-current" : i + 1 < current ? "is-done" : ""}>
          {i + 1}. {label}
        </li>
      ))}
    </ol>
  );
}

function BackToJobs({ label = "Back to jobs" }: { label?: string }) {
  return <Link to={useJobsPath()} className="link-secondary">{label}</Link>;
}

function UploadStep() {
  const { session, startCv } = useSession();
  const pending = session.pendingTailorJobId !== null;
  return (
    <section className="step">
      <Steps current={1} />
      <h1>Upload your CV</h1>
      <p className="muted">
        {pending
          ? "Upload and confirm your CV once. Then you come back to the job you chose and its CV is prepared."
          : "Upload and confirm your CV once. It is used for every job you tailor a CV to."}
      </p>
      <UploadCv onExtracted={startCv} />
      <p><BackToJobs /></p>
    </section>
  );
}

function TextStep() {
  const { session, setCvText, setParsed, resetCv } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const text = session.cv.text ?? "";

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
        File: <strong>{session.cv.fileName}</strong>. This exact text is sent to the language
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
        <BackToJobs />
      </div>
    </section>
  );
}

function ConfirmStep() {
  const { session, setParsed, confirmCv } = useSession();
  const navigate = useNavigate();
  const jobsPath = useJobsPath();
  const parsed = session.cv.parsed!;
  return (
    <section className="step">
      <Steps current={3} />
      <h1>Confirm your CV</h1>
      <p className="muted">
        This is how your CV was understood. Every tailored CV is built from it.
        If something is wrong, go back, fix the text and analyze again.
      </p>
      {parsed.warnings.length > 0 && (
        <div className="warning" role="status">
          <strong>Worth double-checking:</strong>
          <ul>{parsed.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      <div className="actions">
        <button
          type="button"
          className="primary"
          onClick={() => { confirmCv(parsed.cv); navigate(jobsPath); }}
        >
          Confirm CV
        </button>
        <button type="button" onClick={() => setParsed(null)}>Back to text</button>
      </div>
      <CvPreview cv={parsed.cv} />
    </section>
  );
}

function ConfirmedStep() {
  const { session, resetCv } = useSession();
  const cv = session.cv.confirmedCv!;
  return (
    <section className="step">
      <h1>Your CV</h1>
      <p className="muted">
        <span className="ready-mark">✓ Confirmed</span> · {session.cv.fileName}. Tailored CVs are built from this.
      </p>
      <div className="actions">
        <Link to="/" className="button primary">Back to jobs</Link>
        <button type="button" onClick={resetCv}>Upload a different CV</button>
      </div>
      <p className="muted small">Uploading a different CV discards the CVs already tailored from this one.</p>
      <CvPreview cv={cv} />
    </section>
  );
}
