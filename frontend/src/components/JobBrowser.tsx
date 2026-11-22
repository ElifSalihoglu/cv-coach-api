import { MOBILE_QUERY, useMediaQuery } from "../hooks";
import type { FoundJob } from "../types";
import { JobCard } from "./JobCard";
import { JobDetail, type CoachControls } from "./JobDetail";

export type { CoachControls };

interface Props {
  jobs: FoundJob[];
  /** From the URL; on mobile a selected job means the detail view is open. */
  selectedId: string | null;
  onSelect: (jobId: string) => void;
  onBack: () => void;
  coach: CoachControls;
}

/** Results list and job details: side by side on desktop, one at a time on mobile. */
export function JobBrowser({ jobs, selectedId, onSelect, onBack, coach }: Props) {
  const mobile = useMediaQuery(MOBILE_QUERY);
  const chosen = jobs.find((j) => j.id === selectedId) ?? null;
  const shown = mobile ? chosen : chosen ?? jobs[0];

  const list = (
    <div className="job-list" role="list" aria-label="Search results">
      {jobs.map((job) => (
        <div role="listitem" key={job.id}>
          <JobCard
            job={job}
            selected={job.id === shown?.id}
            ready={coach.stateFor(job.id)?.status === "ready"}
            onSelect={onSelect}
          />
        </div>
      ))}
    </div>
  );

  const detail = shown && (
    <div className="detail-pane">
      {mobile && (
        <button type="button" className="link-button back" onClick={onBack}>
          ← Back to results
        </button>
      )}
      <JobDetail key={shown.id} job={shown} controls={coach} />
    </div>
  );

  if (mobile) return shown ? detail : list;
  return (
    <div className="browser">
      {list}
      {detail}
    </div>
  );
}
