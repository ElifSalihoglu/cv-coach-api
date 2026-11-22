import { useState } from "react";
import { fetchCvPdf, saveBlob } from "../api";
import type { DraftAction } from "../coachStore";
import type { FoundJob, JobCoach, StructuredCV } from "../types";
import { ChangesList } from "./ChangesList";
import { CvPreview } from "./CvPreview";
import { FocusPicker } from "./FocusPicker";
import { QuestionCard } from "./QuestionCard";
import { SuggestionCard } from "./SuggestionCard";

export interface CoachControls {
  hasCv: boolean;
  mainCv: StructuredCV | null;
  stateFor: (jobId: string) => JobCoach | undefined;
  start: (job: FoundJob) => void;
  choose: (job: FoundJob, name: string) => void;
  changeFocus: (job: FoundJob) => void;
  decide: (job: FoundJob, action: DraftAction) => void;
}

type Download = "idle" | "downloading" | "failed";

/** One job: its description, the link to the posting, and the coaching for it. */
export function JobDetail({ job, controls }: { job: FoundJob; controls: CoachControls }) {
  const [previewing, setPreviewing] = useState(false);
  const [download, setDownload] = useState<Download>("idle");
  const coach = controls.stateFor(job.id);
  const hasDescription = job.status === "ready" && job.job_description.trim() !== "";

  const result = coach?.focus != null ? coach.results[coach.focus] : undefined;
  const draft = coach?.focus != null ? coach.drafts[coach.focus] : undefined;
  const finalCv = draft?.applied?.cv ?? controls.mainCv; // the main CV until something is accepted
  const changes = draft?.applied?.changes ?? [];
  const mainCv = controls.mainCv;
  const ready = coach?.status === "ready" && result && draft && finalCv && mainCv;

  async function downloadPdf() {
    if (!finalCv) return;
    setDownload("downloading");
    try {
      saveBlob(await fetchCvPdf({ cv: finalCv, company: job.company, title: job.title }));
      setDownload("idle");
    } catch {
      setDownload("failed"); // the draft stays; only the download is retried
    }
  }

  return (
    <article className="detail" aria-label="Job details">
      <header className="detail-head">
        <h3>{job.title}</h3>
        <p className="muted">{job.company} · {job.location}</p>
        {job.source_url && (
          <a href={job.source_url} target="_blank" rel="noreferrer">View original posting</a>
        )}
      </header>

      <section className="cv-action" aria-label="CV for this job">
        {(!coach || coach.status === "error") && (
          <>
            {coach?.status === "error" && <p className="error" role="alert">{coach.message}</p>}
            <button type="button" className="primary" onClick={() => controls.start(job)} disabled={!hasDescription}>
              {coach?.status === "error" ? "Try again" : "Tailor my CV"}
            </button>
            {!hasDescription ? (
              <p className="hint">No job description was found for this posting, so a CV cannot be tailored to it.</p>
            ) : !controls.hasCv && !coach ? (
              <p className="hint">You will upload and confirm your CV first, then come back to this job.</p>
            ) : (
              <p className="hint">You get suggestions to review. Nothing changes in your CV until you accept it.</p>
            )}
          </>
        )}

        {coach?.status === "working" && (
          <p className="status" role="status">Reading the posting against your CV…</p>
        )}

        {coach?.status === "choose" && coach.choice && (
          <FocusPicker choice={coach.choice} message={coach.message} onChoose={(name) => controls.choose(job, name)} />
        )}

        {ready && (
          <div className="coach-ready">
            <p className="coach-focus">
              {coach.focus !== "_" && <>Focus: <strong>{coach.focus}</strong> </>}
              {coach.choice && (
                <button type="button" className="link-button" onClick={() => controls.changeFocus(job)}>
                  Change focus
                </button>
              )}
            </p>

            <PostingSummary result={result} />

            <div className="button-row">
              <button type="button" onClick={() => setPreviewing((v) => !v)} aria-pressed={previewing}>
                Preview CV
              </button>
              <button type="button" className="primary" onClick={downloadPdf}
                      disabled={download === "downloading" || draft.applying}>
                {download === "downloading" ? "Preparing PDF…" : "Download PDF"}
              </button>
            </div>
            {download === "failed" && (
              <div className="error" role="alert">
                <span>Download failed. Your decisions are kept.</span>
                <button type="button" onClick={downloadPdf}>Try again</button>
              </div>
            )}
            {draft.error && <p className="error" role="alert">{draft.error}</p>}

            <h4>Suggestions for this application</h4>
            {result.suggestions.length === 0 ? (
              <p className="muted">
                Nothing worth changing for this focus: your CV already shows what the posting asks for.
              </p>
            ) : (
              <div className="suggestions">
                {result.suggestions.map((s) => (
                  <SuggestionCard
                    key={`${coach.focus}:${s.id}`} suggestion={s} job={job} mainCv={mainCv}
                    decision={draft.decisions[s.id]} rejected={draft.rejected.includes(s.id)}
                    onAction={(a) => controls.decide(job, a)}
                  />
                ))}
              </div>
            )}

            {result.questions.length > 0 && (
              <>
                <h4>Questions about your experience</h4>
                <div className="suggestions">
                  {result.questions.map((q) => (
                    <QuestionCard
                      key={`${coach.focus}:${q.id}`} question={q} job={job} mainCv={mainCv}
                      addition={draft.additions[q.id]} declined={draft.rejected.includes(q.id)}
                      onAction={(a) => controls.decide(job, a)}
                    />
                  ))}
                </div>
              </>
            )}

            {changes.length > 0 ? (
              <ChangesList changes={changes} />
            ) : (
              <p className="changes-none">Nothing accepted yet: the preview and the PDF are your main CV.</p>
            )}
          </div>
        )}
      </section>

      {ready && previewing && finalCv ? (
        <section aria-label="CV preview">
          <button type="button" className="link-button" onClick={() => setPreviewing(false)}>
            Back to job description
          </button>
          {changes.length > 0 && (
            <p className="hint">Highlighted lines are the changes you accepted. The PDF has no highlights.</p>
          )}
          <CvPreview cv={finalCv} changedIds={new Set(changes.map((c) => c.id))} />
        </section>
      ) : (
        <section aria-label="Job description">
          <h4>Job description</h4>
          {hasDescription ? (
            <div className="description">{job.job_description}</div>
          ) : (
            <p className="muted">No description was found for this posting.</p>
          )}
        </section>
      )}
    </article>
  );
}

function PostingSummary({ result }: { result: NonNullable<JobCoach["results"][string]> }) {
  const required = result.requirements.filter((r) => r.level === "required");
  const preferred = result.requirements.filter((r) => r.level === "preferred");
  if (!result.responsibilities.length && !result.requirements.length) return null;
  return (
    <details className="posting-summary">
      <summary>What this posting asks for</summary>
      {result.responsibilities.length > 0 && (
        <>
          <h5>Main responsibilities</h5>
          <ul>{result.responsibilities.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </>
      )}
      {required.length > 0 && (
        <>
          <h5>Required</h5>
          <ul>{required.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
        </>
      )}
      {preferred.length > 0 && (
        <>
          <h5>Preferred</h5>
          <ul>{preferred.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
        </>
      )}
    </details>
  );
}
