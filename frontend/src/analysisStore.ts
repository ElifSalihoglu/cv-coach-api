import { useCallback, useRef, useState } from "react";
import { applyDecisions, type AnalyzeOptions } from "./api";
import {
  AUTO_FOCUS, type Analysis, type AdditionTarget, type CoachDraft, type CoachResult, type StructuredCV,
} from "./types";

/** What the user can do with a suggestion or a question card. */
export type DraftAction =
  | { type: "accept"; id: string }
  | { type: "edit"; id: string; text: string; confirmed: string[] }
  | { type: "reject"; id: string }
  | { type: "undo"; id: string }
  | { type: "answer"; id: string; target: AdditionTarget; text: string; confirmed: string[] }
  | { type: "decline"; id: string };

export const emptyDraft = (): CoachDraft => ({
  decisions: {}, rejected: [], additions: {}, applied: null, applying: false, error: null,
});

const without = <T,>(record: Record<string, T>, key: string) => {
  const { [key]: _removed, ...rest } = record;
  return rest;
};

/** The draft after one action. Pure: nothing is asked of the model or the network. */
export function nextDraft(draft: CoachDraft, action: DraftAction): CoachDraft {
  const notRejected = draft.rejected.filter((x) => x !== action.id);
  switch (action.type) {
    case "accept":
      return { ...draft, decisions: { ...draft.decisions, [action.id]: { action: "accept" } }, rejected: notRejected };
    case "edit":
      return {
        ...draft,
        decisions: { ...draft.decisions, [action.id]: { action: "edit", text: action.text, confirmed_terms: action.confirmed } },
        rejected: notRejected,
      };
    case "reject":
      return { ...draft, decisions: without(draft.decisions, action.id), rejected: [...notRejected, action.id] };
    case "undo":
      return {
        ...draft, decisions: without(draft.decisions, action.id),
        additions: without(draft.additions, action.id), rejected: notRejected,
      };
    case "answer":
      return {
        ...draft,
        additions: {
          ...draft.additions,
          [action.id]: { id: action.id, target: action.target, text: action.text, confirmed_terms: action.confirmed },
        },
        rejected: notRejected,
      };
    case "decline":
      return { ...draft, additions: without(draft.additions, action.id), rejected: [...notRejected, action.id] };
  }
}

const hasWork = (draft: CoachDraft) =>
  Object.keys(draft.decisions).length + Object.keys(draft.additions).length > 0;

const failure = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback);

const working = (options: AnalyzeOptions): Analysis => ({
  posting: options.posting, domain: options.domain, careerGoal: options.careerGoal,
  status: "working", message: null, choice: null, focus: null, results: {}, drafts: {},
});

type Analyze = (cv: StructuredCV, options: AnalyzeOptions, focus: string) => Promise<CoachResult>;

/**
 * The analysis of one posting: one model call per focus, then reused, and the user's decisions.
 * Deciding, undoing and downloading never reach the model: the accepted decisions go to a
 * deterministic endpoint that returns the draft CV. The main CV is only ever an input.
 */
export function useAnalysisStore(mainCv: StructuredCV | null, analyze?: Analyze) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const latest = useRef(analysis);
  const cvRef = useRef(mainCv);
  cvRef.current = mainCv;
  const generation = useRef(0); // bumped when the analysis restarts: older answers are dropped
  const applySeq = useRef<Record<string, number>>({});

  const update = useCallback((fn: (current: Analysis | null) => Analysis | null) => {
    latest.current = fn(latest.current);
    setAnalysis(latest.current);
  }, []);
  const patch = useCallback(
    (fn: (current: Analysis) => Analysis) => update((current) => (current ? fn(current) : current)),
    [update],
  );

  /** Drop the analysis and every answer still on its way. */
  const reset = useCallback(() => {
    generation.current += 1;
    applySeq.current = {};
    update(() => null);
  }, [update]);

  const show = useCallback(
    (focus: string, result: CoachResult) =>
      patch((c) => ({
        ...c, status: "ready", message: null, focus,
        results: { ...c.results, [focus]: result },
        drafts: { ...c.drafts, [focus]: c.drafts[focus] ?? emptyDraft() },
      })),
    [patch],
  );

  /** Ready-made suggestions (the demo): no analysis is asked for. */
  const seed = useCallback(
    (options: AnalyzeOptions, result: CoachResult) => {
      reset();
      update(() => ({
        ...working(options), status: "ready", focus: AUTO_FOCUS,
        results: { [AUTO_FOCUS]: result }, drafts: { [AUTO_FOCUS]: emptyDraft() },
      }));
    },
    [reset, update],
  );

  const start = useCallback(
    async (options: AnalyzeOptions) => {
      const cv = cvRef.current;
      if (!cv || !analyze) return;
      reset();
      const gen = generation.current;
      update(() => working(options));
      try {
        const result = await analyze(cv, options, "");
        if (gen !== generation.current) return;
        if (result.kind === "suggestions") {
          show(AUTO_FOCUS, result);
        } else {
          patch((c) => ({ ...c, status: "choose", choice: result, message: null }));
        }
      } catch (err) {
        if (gen !== generation.current) return;
        patch((c) => ({ ...c, status: "error", message: failure(err, "The analysis failed.") }));
      }
    },
    [analyze, patch, reset, show, update],
  );

  const choose = useCallback(
    async (name: string) => {
      const current = latest.current;
      const cv = cvRef.current;
      if (!current || current.status === "working" || !cv || !analyze) return;
      if (current.results[name]) {
        patch((c) => ({ ...c, status: "ready", focus: name, message: null })); // reused, never asked again
        return;
      }
      const gen = generation.current;
      patch((c) => ({ ...c, status: "working", message: null }));
      try {
        const result = await analyze(cv, current, name);
        if (gen === generation.current) show(name, result);
      } catch (err) {
        if (gen !== generation.current) return;
        patch((c) => ({
          ...c, status: c.choice ? "choose" : "error", message: failure(err, "The analysis failed."),
        }));
      }
    },
    [analyze, patch, show],
  );

  const changeFocus = useCallback(
    () => patch((c) => (c.choice ? { ...c, status: "choose", message: null } : c)),
    [patch],
  );

  const decide = useCallback(
    async (action: DraftAction) => {
      const current = latest.current;
      const cv = cvRef.current;
      const key = current?.focus;
      if (!current || key == null || !cv) return;
      const result = current.results[key];
      const draft = nextDraft(current.drafts[key] ?? emptyDraft(), action);
      const work = hasWork(draft);
      patch((c) => ({
        ...c,
        drafts: { ...c.drafts, [key]: { ...draft, applied: work ? draft.applied : null, applying: work, error: null } },
      }));
      if (!work) return;
      const token = (applySeq.current[key] = (applySeq.current[key] ?? 0) + 1);
      const gen = generation.current;
      try {
        const applied = await applyDecisions({
          cv, suggestions: result.suggestions, decisions: draft.decisions,
          additions: Object.values(draft.additions), job_description: current.posting.description,
        });
        if (applySeq.current[key] !== token || gen !== generation.current) return;
        patch((c) => ({ ...c, drafts: { ...c.drafts, [key]: { ...c.drafts[key], applied, applying: false, error: null } } }));
      } catch (err) {
        if (applySeq.current[key] !== token || gen !== generation.current) return;
        patch((c) => ({
          ...c,
          drafts: { ...c.drafts, [key]: { ...c.drafts[key], applying: false, error: failure(err, "Could not apply your decision.") } },
        }));
      }
    },
    [patch],
  );

  return { analysis, start, choose, changeFocus, decide, seed, reset };
}

export type AnalysisStore = ReturnType<typeof useAnalysisStore>;
