import type { FoundJob } from "../types";

interface Props { job: FoundJob; selected: boolean; ready: boolean; onSelect: (id: string) => void }

export function JobCard({ job, selected, ready, onSelect }: Props) {
  return (
    <button
      type="button"
      className={`job-card${selected ? " is-selected" : ""}`}
      aria-pressed={selected}
      onClick={() => onSelect(job.id)}
    >
      <span className="job-title">{job.title}</span>
      <span className="job-company">{job.company}</span>
      <span className="job-location">{job.location}</span>
      {ready && <span className="job-flag">CV ready</span>}
    </button>
  );
}
