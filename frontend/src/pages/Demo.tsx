import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useCoachStore } from "../coachStore";
import { JobBrowser } from "../components/JobBrowser";
import { DEMO_JOBS, DEMO_MAIN_CV } from "../data/demo";
import { MOBILE_QUERY, useMediaQuery } from "../hooks";
import type { FoundJob } from "../types";

const JOBS = DEMO_JOBS.map((d) => d.job);

/**
 * The sample results screen: synthetic jobs and a synthetic candidate. The suggestions are
 * ready-made, so no upload and no model call are involved; deciding works as in the real flow.
 */
export function Demo() {
  const store = useCoachStore(DEMO_MAIN_CV);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const mobile = useMediaQuery(MOBILE_QUERY);

  function start(job: FoundJob) {
    const demo = DEMO_JOBS.find((d) => d.job.id === job.id);
    if (demo) store.seed(job, demo.result);
  }

  return (
    <>
      <div className="page-title">
        <h1>Demo</h1>
        <span className="badge">Demo data</span>
        <Link to="/" className="link-secondary">Search real jobs</Link>
      </div>
      <p className="muted">
        Two sample jobs and a sample candidate. The suggestions are ready-made; you decide which ones go into the CV.
      </p>
      <section className="results-section" aria-label="Demo results">
        <JobBrowser
          jobs={JOBS}
          selectedId={params.get("job")}
          onSelect={(id) => setParams({ job: id }, { replace: !mobile, state: { fromList: true } })}
          onBack={() => (location.state?.fromList ? navigate(-1) : setParams({}, { replace: true }))}
          coach={{
            hasCv: true,
            mainCv: DEMO_MAIN_CV,
            stateFor: (id) => store.coach[id],
            start,
            choose: (job, name) => void store.choose(job, name),
            changeFocus: store.changeFocus,
            decide: (job, action) => void store.decide(job, action),
          }}
        />
      </section>
    </>
  );
}
