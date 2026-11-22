import { useState } from "react";
import { fetchCvPdf, saveBlob } from "../api";
import type { FoundJob, TailorState } from "../types";
import { CvPreview } from "./CvPreview";

interface Props {
  job: FoundJob;
  state: TailorState | undefined;
  hasCv: boolean;
  onTailor: () => void;
}

type Download = "idle" | "downloading" | "failed";

/** One job: its description, the link to the posting, and the CV actions for it. */
export function JobDetail({ job, state, hasCv, onTailor }: Props) {
  const [previewing, setPreviewing] = useState(false);
  const [download, setDownload] = useState<Download>("idle");
  const hasDescription = job.status === "ready" && job.job_description.trim() !== "";

  async function downloadPdf() {
    if (state?.status !== "ready") return;
    setDownload("downloading");
    try {
      saveBlob(await fetchCvPdf({ cv: state.cv, company: job.company, title: job.title }));
      setDownload("idle");
    } catch {
      setDownload("failed"); // the prepared CV stays; only the download is retried
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
        {(!state || state.status === "error") && (
          <>
            {state?.status === "error" && (
              <p className="error" role="alert">{state.message}</p>
            )}
            <button type="button" className="primary" onClick={onTailor} disabled={!hasDescription}>
              {state?.status === "error" ? "Try again" : "Tailor my CV"}
            </button>
            {!hasDescription ? (
              <p className="hint">No job description was found for this posting, so a CV cannot be tailored to it.</p>
            ) : !hasCv && !state ? (
              <p className="hint">You will upload and confirm your CV first, then come back to this job.</p>
            ) : null}
          </>
        )}

        {state?.status === "working" && (
          <p className="status" role="status">Tailoring your CV for this job…</p>
        )}

        {state?.status === "ready" && (
          <>
            <p className="status-ready">✓ CV ready for this job</p>
            <div className="button-row">
              <button type="button" onClick={() => setPreviewing((v) => !v)} aria-pressed={previewing}>
                Preview CV
              </button>
              <button type="button" className="primary" onClick={downloadPdf} disabled={download === "downloading"}>
                {download === "downloading" ? "Preparing PDF…" : "Download PDF"}
              </button>
            </div>
            {download === "failed" && (
              <div className="error" role="alert">
                <span>Download failed. Your CV is still ready.</span>
                <button type="button" onClick={downloadPdf}>Try again</button>
              </div>
            )}
            {state.warnings.length > 0 && (
              <details className="notes">
                <summary>Notes about this CV ({state.warnings.length})</summary>
                <ul>{state.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </details>
            )}
          </>
        )}
      </section>

      {state?.status === "ready" && previewing ? (
        <section aria-label="CV preview">
          <button type="button" className="link-button" onClick={() => setPreviewing(false)}>
            Back to job description
          </button>
          <CvPreview cv={state.cv} />
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
