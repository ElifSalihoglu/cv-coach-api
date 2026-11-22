import { useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { JobBrowser } from "../components/JobBrowser";
import { DEMO_JOBS } from "../data/demo";
import { MOBILE_QUERY, useMediaQuery } from "../hooks";
import type { FoundJob, TailorState } from "../types";

const JOBS = DEMO_JOBS.map((d) => d.job);

/**
 * The sample results screen: synthetic jobs and a synthetic candidate. "Tailor my CV"
 * shows the ready-made demo CV, so no upload and no model call are involved.
 */
export function Demo() {
  const [tailored, setTailored] = useState<Record<string, TailorState>>({});
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const mobile = useMediaQuery(MOBILE_QUERY);

  function request(job: FoundJob) {
    const demo = DEMO_JOBS.find((d) => d.job.id === job.id);
    if (demo) setTailored((t) => ({ ...t, [job.id]: { status: "ready", cv: demo.cv, warnings: [], changes: demo.changes } }));
  }

  return (
    <>
      <div className="page-title">
        <h1>Demo</h1>
        <span className="badge">Demo data</span>
        <Link to="/" className="link-secondary">Search real jobs</Link>
      </div>
      <p className="muted">
        Two sample jobs and a sample candidate. Tailoring here shows a ready-made CV.
      </p>
      <section className="results-section" aria-label="Demo results">
        <JobBrowser
          jobs={JOBS}
          selectedId={params.get("job")}
          onSelect={(id) => setParams({ job: id }, { replace: !mobile, state: { fromList: true } })}
          onBack={() => (location.state?.fromList ? navigate(-1) : setParams({}, { replace: true }))}
          tailor={{ hasCv: true, stateFor: (id) => tailored[id], request }}
        />
      </section>
    </>
  );
}
