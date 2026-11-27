// Mirrors app/models/cv_document.py (StructuredCV).
export interface CVBullet { id: string; text: string }
export interface CVExperience {
  id: string; employer: string; title: string; start: string; end: string;
  location: string; bullets: CVBullet[];
}
export interface CVEducation {
  id: string; school: string; degree: string; start: string; end: string; details: string;
}
export interface CVProject { id: string; name: string; description: string }
export interface CVCertification { id: string; name: string; issuer: string; date: string }

export interface StructuredCV {
  name: string; email: string; phone: string; location: string; links: string[];
  summary: string;
  experiences: CVExperience[];
  education: CVEducation[];
  skills: string[];
  projects: CVProject[];
  certifications: CVCertification[];
  languages: string[];
}

/** The job posting the user pastes, with an optional company for the PDF file name. */
export interface Posting { title: string; description: string; company: string }

/** What the PDF endpoint needs: the CV to print and the job it was made for. */
export interface PdfSource { cv: StructuredCV; company: string; title: string }

/** One difference between the confirmed CV and a tailored CV. `id` is "summary" or a bullet id. */
export interface CvChange {
  kind: "moved" | "summary" | "rewritten" | "moved_rewritten" | "added";
  id: string;
  where: string;
  before: string;
  after: string;
  detail: string;
  /** The user wrote this or confirmed a claim the CV did not make. */
  user_added?: boolean;
  suggestion_id?: string;
}

// ---- Career coach (mirrors app/models/coaching.py and the orchestration records) ----

export type Level = "required" | "preferred";

export interface Requirement { text: string; quote: string; level: Level }
export interface SourceRef { id: string; where: string; text: string }
export interface Evidence { source_id: string; where: string; text: string; why: string }

export interface FocusOption {
  id: string; name: string; quote: string; summary: string;
  coverage: "strong" | "partial" | "none"; evidence: Evidence[]; note: string;
}

export interface Suggestion {
  id: string; // "promote:exp1.b4", "rewrite:exp1.b2" or "summary"
  kind: "promote" | "rewrite" | "summary";
  requirement: string; level: Level;
  sources: SourceRef[];
  support: "direct" | "related";
  before: string; after: string;
  position: number | null;
  rationale: string; priority: number;
}

export interface Question { id: string; requirement: string; level: Level; term: string; text: string }

export interface RoutingDecision {
  primary: string; // agent id
  method: "override" | "rules" | "fallback";
  confidence: "high" | "low";
  reasons: string[]; // codes such as "title_cue:software engineer" or "agent_failed:it"
}
export interface AgentRun { agent_id: string; status: "ok" | "failed"; duration_ms: number; error_code: string }

/** Which agent answered and why, as reported by the API. */
export interface CoachMeta {
  routing: RoutingDecision;
  runs: AgentRun[];
  provenance: Record<string, string>; // suggestion, question or track id -> agent id
}

export interface CoachResult {
  kind: "suggestions" | "choose_focus";
  focus: string;
  responsibilities: string[];
  requirements: Requirement[];
  tracks: FocusOption[];
  suggestions: Suggestion[];
  questions: Question[];
  dropped: number; // model proposals our checks removed
  dropped_reasons: Record<string, number>; // why, as codes
  meta: CoachMeta | null;
}

export interface Claim { kind: "numbers" | "seniority" | "skills"; terms: string[] }

/** What the user decided about one suggestion. Rejected and undecided ones are not sent. */
export type Decision =
  | { action: "accept" }
  | { action: "edit"; text: string; confirmed_terms: string[] };

export interface AdditionTarget { type: "experience" | "project"; id: string }
export interface Addition { id: string; target: AdditionTarget; text: string; confirmed_terms: string[] }

export interface AppliedCv { cv: StructuredCV; changes: CvChange[] }

/** The user's draft CV for one job and one focus. The main CV is never part of it. */
export interface CoachDraft {
  decisions: Record<string, Decision>;
  rejected: string[]; // suggestion ids and question ids the user turned down
  additions: Record<string, Addition>;
  applied: AppliedCv | null; // null until something is accepted: then the draft is the main CV
  applying: boolean; // a decision is being turned into the draft CV (no model involved)
  error: string | null;
}

/** The analysis of one posting: the answers so far and the user's draft for each focus. */
export interface Analysis {
  posting: Posting;
  domain: string; // "" = automatic
  careerGoal: string;
  status: "working" | "choose" | "ready" | "error";
  message: string | null;
  choice: CoachResult | null; // the tracks to choose from, if the posting had several
  focus: string | null; // key of the shown result: a track name, or AUTO_FOCUS
  results: Record<string, CoachResult>; // every focus already analysed: reused, never asked again
  drafts: Record<string, CoachDraft>;
}

/** Result key when the posting needed no choice. */
export const AUTO_FOCUS = "_";
