import {
  createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode,
} from "react";
import { ApiError, errorMessage, searchJobs, tailorCv, type ParsedCv } from "./api";
import type { FoundJob, StructuredCV, TailorState } from "./types";

/** The analysed CV while the user reviews it: the user's edits live here, not in the API result. */
export interface ParsedDraft extends ParsedCv {
  edited: boolean;
  /** Sections the user already saved; their parse warnings are no longer shown. */
  reviewed: string[];
}

export interface CvSession {
  fileName: string | null;
  text: string | null; // extracted text, editable until analyzed
  parsed: ParsedDraft | null; // analysis result awaiting confirmation
  confirmedCv: StructuredCV | null;
}

export type SearchRun =
  | { status: "idle" }
  | { status: "searching" }
  | { status: "error"; message: string; code: string | null }
  | { status: "done" };

export interface SearchSession {
  query: string;
  location: string;
  /** The query that produced `jobs` (the form may have been edited since). */
  searched: { query: string; location: string } | null;
  run: SearchRun;
  jobs: FoundJob[];
}

/**
 * Everything the user has done in this browser session. Kept in memory only:
 * a reload starts over and nothing is written to disk. Search results, the
 * confirmed CV and every tailored CV survive moving between pages, so browsing
 * jobs never repeats a search or a model call.
 */
export interface Session {
  cv: CvSession;
  search: SearchSession;
  tailored: Record<string, TailorState>;
  /** Job the user asked to tailor before having a confirmed CV. */
  pendingTailorJobId: string | null;
}

const EMPTY_CV: CvSession = { fileName: null, text: null, parsed: null, confirmedCv: null };

const INITIAL: Session = {
  cv: EMPTY_CV,
  search: { query: "", location: "", searched: null, run: { status: "idle" }, jobs: [] },
  tailored: {},
  pendingTailorJobId: null,
};

interface Ctx {
  session: Session;
  setSearchForm: (patch: Partial<Pick<SearchSession, "query" | "location">>) => void;
  runSearch: () => Promise<void>;
  startCv: (fileName: string, text: string) => void;
  setCvText: (text: string) => void;
  setParsed: (parsed: ParsedCv | null) => void;
  /** Keep the user's edit of one section of the analysed CV. */
  saveParsedEdit: (cv: StructuredCV, section: string) => void;
  confirmCv: (cv: StructuredCV) => void;
  resetCv: () => void;
  setPendingTailor: (jobId: string | null) => void;
  /** One model call for one job; does nothing if it is running or already done. */
  tailorJob: (job: FoundJob) => Promise<void>;
}

const SessionContext = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>(INITIAL);
  const latest = useRef(session);
  latest.current = session;
  const inflight = useRef(new Set<string>());
  const cvVersion = useRef(0); // bumped when the CV changes, to drop stale model answers

  const setSearch = useCallback(
    (patch: Partial<SearchSession>) =>
      setSession((s) => ({ ...s, search: { ...s.search, ...patch } })),
    [],
  );
  const setCv = useCallback(
    (patch: Partial<CvSession>) => setSession((s) => ({ ...s, cv: { ...s.cv, ...patch } })),
    [],
  );

  const runSearch = useCallback(async () => {
    const { query, location, run } = latest.current.search;
    if (run.status === "searching" || !query.trim() || !location.trim()) return;
    const asked = { query: query.trim(), location: location.trim() };
    setSearch({ run: { status: "searching" } });
    try {
      const jobs = await searchJobs({ query: asked.query, city: asked.location });
      setSearch({ jobs, searched: asked, run: { status: "done" } });
    } catch (err) {
      // The CV and any earlier tailored CVs are untouched; only this run failed.
      setSearch({
        run: {
          status: "error",
          message: errorMessage(err, "The job search failed."),
          code: err instanceof ApiError ? err.code : null,
        },
      });
    }
  }, [setSearch]);

  const tailorJob = useCallback(async (job: FoundJob) => {
    const cv = latest.current.cv.confirmedCv;
    const existing = latest.current.tailored[job.id];
    if (!cv || inflight.current.has(job.id) || existing?.status === "ready") return;
    const version = cvVersion.current;
    inflight.current.add(job.id);
    const put = (state: TailorState) =>
      setSession((s) => ({ ...s, tailored: { ...s.tailored, [job.id]: state } }));
    put({ status: "working" });
    try {
      const result = await tailorCv(cv, job);
      if (version === cvVersion.current) put({ status: "ready", ...result });
    } catch (err) {
      if (version === cvVersion.current) {
        put({ status: "error", message: errorMessage(err, "Could not tailor your CV.") });
      }
    } finally {
      inflight.current.delete(job.id);
    }
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      session,
      setSearchForm: (patch) => setSearch(patch),
      runSearch,
      startCv: (fileName, text) => {
        cvVersion.current += 1;
        setSession((s) => ({
          ...s,
          cv: { fileName, text, parsed: null, confirmedCv: null },
          tailored: {}, // tailored CVs belong to the CV they were made from
        }));
      },
      setCvText: (text) => setCv({ text }),
      setParsed: (parsed) =>
        setCv({ parsed: parsed ? { ...parsed, edited: false, reviewed: [] } : null }),
      saveParsedEdit: (cv, section) =>
        setSession((s) =>
          s.cv.parsed
            ? {
                ...s,
                cv: {
                  ...s.cv,
                  parsed: {
                    ...s.cv.parsed, cv, edited: true,
                    reviewed: [...new Set([...s.cv.parsed.reviewed, section])],
                  },
                },
              }
            : s,
        ),
      confirmCv: (cv) => setCv({ confirmedCv: cv }),
      resetCv: () => {
        cvVersion.current += 1;
        setSession((s) => ({ ...s, cv: EMPTY_CV, tailored: {}, pendingTailorJobId: null }));
      },
      setPendingTailor: (jobId) => setSession((s) => ({ ...s, pendingTailorJobId: jobId })),
      tailorJob,
    }),
    [session, setSearch, setCv, runSearch, tailorJob],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
