import {
  createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode,
} from "react";
import { ApiError, analyzeJob, errorMessage, searchJobs, type ParsedCv } from "./api";
import { useCoachStore, type CoachStore } from "./coachStore";
import type { FoundJob, StructuredCV } from "./types";

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
 * confirmed CV and every job's coaching (analysis and decisions) survive moving
 * between pages, so browsing jobs never repeats a search or a model call.
 * Coaching belongs to the confirmed CV: a new CV starts it over.
 */
export interface Session {
  cv: CvSession;
  search: SearchSession;
  /** Job the user asked to tailor before having a confirmed CV. */
  pendingTailorJobId: string | null;
}

const EMPTY_CV: CvSession = { fileName: null, text: null, parsed: null, confirmedCv: null };

const INITIAL: Session = {
  cv: EMPTY_CV,
  search: { query: "", location: "", searched: null, run: { status: "idle" }, jobs: [] },
  pendingTailorJobId: null,
};

interface Ctx {
  session: Session;
  /** Per-job coaching: analysis results, focus and the user's decisions. */
  coach: CoachStore;
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
}

const SessionContext = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>(INITIAL);
  const latest = useRef(session);
  latest.current = session;
  const coach = useCoachStore(session.cv.confirmedCv, analyzeJob);
  const resetCoach = coach.reset;

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
      // The CV and the coaching done so far are untouched; only this run failed.
      setSearch({
        run: {
          status: "error",
          message: errorMessage(err, "The job search failed."),
          code: err instanceof ApiError ? err.code : null,
        },
      });
    }
  }, [setSearch]);

  const value = useMemo<Ctx>(
    () => ({
      session,
      coach,
      setSearchForm: (patch) => setSearch(patch),
      runSearch,
      startCv: (fileName, text) => {
        resetCoach(); // suggestions belong to the CV they were made from
        setSession((s) => ({ ...s, cv: { fileName, text, parsed: null, confirmedCv: null } }));
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
      confirmCv: (cv) => {
        resetCoach(); // a newly confirmed CV never inherits old suggestions
        setCv({ confirmedCv: cv });
      },
      resetCv: () => {
        resetCoach();
        setSession((s) => ({ ...s, cv: EMPTY_CV, pendingTailorJobId: null }));
      },
      setPendingTailor: (jobId) => setSession((s) => ({ ...s, pendingTailorJobId: jobId })),
    }),
    [session, coach, setSearch, setCv, runSearch, resetCoach],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
