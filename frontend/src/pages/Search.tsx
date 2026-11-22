import { useEffect, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { CvCard } from "../components/CvCard";
import { JobBrowser } from "../components/JobBrowser";
import { MOBILE_QUERY, useMediaQuery } from "../hooks";
import { useSession } from "../session";
import type { FoundJob } from "../types";

/** Home: search first; the CV is only needed when tailoring a CV to a job. */
export function Search() {
  const { session, coach, setSearchForm, runSearch, setPendingTailor } = useSession();
  const { search, cv, pendingTailorJobId } = session;
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const mobile = useMediaQuery(MOBILE_QUERY);
  const selectedId = params.get("job");
  const detailOpen = mobile && search.jobs.some((j) => j.id === selectedId);

  // Back from the CV pages: the job the user wanted a CV for starts tailoring.
  useEffect(() => {
    if (!pendingTailorJobId || !cv.confirmedCv) return;
    const job = search.jobs.find((j) => j.id === pendingTailorJobId);
    setPendingTailor(null);
    if (job) void coach.start(job);
  }, [pendingTailorJobId, cv.confirmedCv, search.jobs, setPendingTailor, coach.start]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setParams({}, { replace: true });
    void runSearch();
  }

  function request(job: FoundJob) {
    if (cv.confirmedCv) {
      void coach.start(job);
      return;
    }
    setPendingTailor(job.id); // after upload and confirmation the user returns here
    navigate("/cv");
  }

  const searching = search.run.status === "searching";
  return (
    <>
      {!detailOpen && (
        <section className="search-section" aria-labelledby="search-title">
          <div className="search-main">
            <h1 id="search-title">Find your next role</h1>
            <p className="lead">
              Search jobs, read the postings, and download a CV tailored to the one you like.
            </p>
            <form className="search-form" onSubmit={onSubmit}>
              <label className="field">
                <span>Role or keyword</span>
                <input
                  value={search.query}
                  onChange={(e) => setSearchForm({ query: e.target.value })}
                  placeholder="e.g. AI Engineer"
                  required
                />
              </label>
              <label className="field">
                <span>City or remote</span>
                <input
                  value={search.location}
                  onChange={(e) => setSearchForm({ location: e.target.value })}
                  placeholder="e.g. Berlin"
                  required
                />
              </label>
              <button type="submit" className="primary" disabled={searching}>
                {searching ? "Searching…" : "Search jobs"}
              </button>
            </form>
            <p className="muted small">
              No CV needed to search. Or just <Link to="/demo">explore a demo</Link>.
            </p>
          </div>
          <CvCard />
        </section>
      )}

      <section className="results-section" aria-labelledby="results-title">
        {!detailOpen && <h2 id="results-title">Results</h2>}

        {search.run.status === "idle" && search.jobs.length === 0 && (
          <p className="notice">Search for a role to see jobs here.</p>
        )}

        {searching && (
          <p className="notice" role="status">
            Searching Indeed and reading each job description. This can take a few minutes.
          </p>
        )}

        {search.run.status === "error" && (
          <div className="error stacked" role="alert">
            <strong>
              {search.run.code === "human_verification"
                ? "Indeed asked for a human verification."
                : "The search did not finish."}
            </strong>
            <span>{search.run.message}</span>
          </div>
        )}

        {search.run.status === "done" && search.jobs.length === 0 && search.searched && (
          <p className="notice" role="status">
            No jobs found for “{search.searched.query}” in {search.searched.location}. Try a
            different role or city.
          </p>
        )}

        {search.jobs.length > 0 && (
          <>
            {!detailOpen && search.searched && (
              <p className="muted">
                {search.jobs.length} {search.jobs.length === 1 ? "job" : "jobs"} for
                “{search.searched.query}” in {search.searched.location}
              </p>
            )}
            <JobBrowser
              jobs={search.jobs}
              selectedId={selectedId}
              onSelect={(id) =>
                setParams({ job: id }, { replace: !mobile, state: { fromList: true } })
              }
              onBack={() =>
                location.state?.fromList ? navigate(-1) : setParams({}, { replace: true })
              }
              coach={{
                hasCv: Boolean(cv.confirmedCv),
                mainCv: cv.confirmedCv,
                stateFor: (id) => coach.coach[id],
                start: request,
                choose: (job, name) => void coach.choose(job, name),
                changeFocus: coach.changeFocus,
                decide: (job, action) => void coach.decide(job, action),
              }}
            />
          </>
        )}
      </section>
    </>
  );
}
