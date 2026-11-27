import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { analyzePosting, type ParsedCv } from "./api";
import { useAnalysisStore, type AnalysisStore } from "./analysisStore";
import type { StructuredCV } from "./types";

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

const EMPTY_CV: CvSession = { fileName: null, text: null, parsed: null, confirmedCv: null };

interface Ctx {
  cv: CvSession;
  /** The analysis of the current posting and the user's decisions on it. */
  analysis: AnalysisStore;
  startCv: (fileName: string, text: string) => void;
  setCvText: (text: string) => void;
  setParsed: (parsed: ParsedCv | null) => void;
  /** Keep the user's edit of one section of the analysed CV. */
  saveParsedEdit: (cv: StructuredCV, section: string) => void;
  confirmCv: (cv: StructuredCV) => void;
  resetCv: () => void;
}

const SessionContext = createContext<Ctx | null>(null);

/**
 * Everything the user has done in this browser session, in memory only: a reload starts over and
 * nothing is written to disk. The analysis belongs to the confirmed CV: a new CV starts it over.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [cv, setCvSession] = useState<CvSession>(EMPTY_CV);
  const analysis = useAnalysisStore(cv.confirmedCv, analyzePosting);
  const resetAnalysis = analysis.reset;

  const value = useMemo<Ctx>(
    () => ({
      cv,
      analysis,
      startCv: (fileName, text) => {
        resetAnalysis();
        setCvSession({ fileName, text, parsed: null, confirmedCv: null });
      },
      setCvText: (text) => setCvSession((s) => ({ ...s, text })),
      setParsed: (parsed) =>
        setCvSession((s) => ({ ...s, parsed: parsed ? { ...parsed, edited: false, reviewed: [] } : null })),
      saveParsedEdit: (edited, section) =>
        setCvSession((s) =>
          s.parsed
            ? {
                ...s,
                parsed: {
                  ...s.parsed, cv: edited, edited: true,
                  reviewed: [...new Set([...s.parsed.reviewed, section])],
                },
              }
            : s,
        ),
      confirmCv: (confirmed) => {
        resetAnalysis(); // a newly confirmed CV never inherits old suggestions
        setCvSession((s) => ({ ...s, confirmedCv: confirmed }));
      },
      resetCv: () => {
        resetAnalysis();
        setCvSession(EMPTY_CV);
      },
    }),
    [cv, analysis, resetAnalysis],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
