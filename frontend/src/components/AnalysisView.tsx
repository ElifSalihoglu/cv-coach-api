import { useState } from "react";
import { fetchCvPdf, saveBlob } from "../api";
import type { DraftAction } from "../analysisStore";
import type { Analysis, CoachResult, StructuredCV } from "../types";
import { AgentPanel } from "./AgentPanel";
import { ChangesList } from "./ChangesList";
import { CvPreview } from "./CvPreview";
import { FocusPicker } from "./FocusPicker";
import { QuestionCard } from "./QuestionCard";
import { SuggestionCard } from "./SuggestionCard";

export interface AnalysisControls {
  choose: (focus: string) => void;
  changeFocus: () => void;
  decide: (action: DraftAction) => void;
  /** Ask again after a failure. */
  retry: () => void;
  /** Leave this posting and start another one; absent where there is only one (the demo). */
  reset?: () => void;
}

type Download = "idle" | "downloading" | "failed";

interface Props {
  analysis: Analysis;
  mainCv: StructuredCV;
  controls: AnalysisControls;
}

/** One analysed posting: which agent answered, the suggestions with their evidence, and the CV. */
export function AnalysisView({ analysis, mainCv, controls }: Props) {
  const [previewing, setPreviewing] = useState(false);
  const [download, setDownload] = useState<Download>("idle");
  const { posting } = analysis;

  const result = analysis.focus != null ? analysis.results[analysis.focus] : undefined;
  const draft = analysis.focus != null ? analysis.drafts[analysis.focus] : undefined;
  const finalCv = draft?.applied?.cv ?? mainCv; // the main CV until something is accepted
  const changes = draft?.applied?.changes ?? [];
  const ready = analysis.status === "ready" && result && draft;

  async function downloadPdf() {
    setDownload("downloading");
    try {
      saveBlob(await fetchCvPdf({ cv: finalCv, company: posting.company, title: posting.title }));
      setDownload("idle");
    } catch {
      setDownload("failed"); // the draft stays; only the download is retried
    }
  }

  return (
    <article className="analysis" aria-label="Analysis">
      <header className="analysis-head">
        <div>
          <h2>{posting.title}</h2>
          {posting.company && <p className="muted">{posting.company}</p>}
        </div>
        {controls.reset && <button type="button" onClick={controls.reset}>Analyze a different posting</button>}
      </header>

      {analysis.status === "working" && (
        <p className="status" role="status">Reading the posting against your CV… this can take up to a minute.</p>
      )}

      {analysis.status === "error" && (
        <div className="error stacked" role="alert">
          <strong>The analysis did not finish.</strong>
          <span>{analysis.message}</span>
          <button type="button" onClick={controls.retry}>Try again</button>
        </div>
      )}

      {analysis.status === "choose" && analysis.choice && (
        <>
          <AgentPanel meta={analysis.choice.meta} dropped={analysis.choice.dropped} droppedReasons={analysis.choice.dropped_reasons} />
          <FocusPicker choice={analysis.choice} message={analysis.message} onChoose={controls.choose} />
        </>
      )}

      {ready && (
        <div className="coach-ready">
          <AgentPanel meta={result.meta} dropped={result.dropped} droppedReasons={result.dropped_reasons} />
          <p className="coach-focus">
            {analysis.focus !== "_" && <>Focus: <strong>{analysis.focus}</strong> </>}
            {analysis.choice && (
              <button type="button" className="link-button" onClick={controls.changeFocus}>Change focus</button>
            )}
          </p>

          <PostingSummary result={result} />

          <h3>Suggestions for this application</h3>
          <p className="hint">You decide: nothing changes in your CV until you accept a suggestion, and every one can be undone.</p>
          {result.suggestions.length === 0 ? (
            <p className="notice">
              Nothing worth changing for this focus: your CV already shows what the posting asks for.
            </p>
          ) : (
            <div className="suggestions">
              {result.suggestions.map((s) => (
                <SuggestionCard
                  key={`${analysis.focus}:${s.id}`} suggestion={s} jobDescription={posting.description} mainCv={mainCv}
                  decision={draft.decisions[s.id]} rejected={draft.rejected.includes(s.id)}
                  onAction={controls.decide}
                />
              ))}
            </div>
          )}

          {result.questions.length > 0 && (
            <>
              <h3>Questions about your experience</h3>
              <div className="suggestions">
                {result.questions.map((q) => (
                  <QuestionCard
                    key={`${analysis.focus}:${q.id}`} question={q} jobDescription={posting.description} mainCv={mainCv}
                    addition={draft.additions[q.id]} declined={draft.rejected.includes(q.id)}
                    onAction={controls.decide}
                  />
                ))}
              </div>
            </>
          )}

          <h3>Your updated CV</h3>
          {changes.length > 0 ? (
            <ChangesList changes={changes} />
          ) : (
            <p className="changes-none">Nothing accepted yet: the preview and the PDF are your main CV.</p>
          )}
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
          {previewing && (
            <section aria-label="CV preview">
              {changes.length > 0 && (
                <p className="hint">Highlighted lines are the changes you accepted. The PDF has no highlights.</p>
              )}
              <CvPreview cv={finalCv} changedIds={new Set(changes.map((c) => c.id))} />
            </section>
          )}
        </div>
      )}

      <details className="posting-text">
        <summary>Job posting</summary>
        <div className="description">{posting.description}</div>
      </details>
    </article>
  );
}

function PostingSummary({ result }: { result: CoachResult }) {
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
