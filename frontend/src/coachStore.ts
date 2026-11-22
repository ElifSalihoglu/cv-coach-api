import { useCallback, useRef, useState } from "react";
import { applyDecisions } from "./api";
import {
  AUTO_FOCUS, type AdditionTarget, type CoachDraft, type CoachResult, type FoundJob, type JobCoach,
  type StructuredCV,
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

const blank = (): JobCoach => ({
  status: "working", message: null, choice: null, focus: null, results: {}, drafts: {},
});

type Analyze = (cv: StructuredCV, job: FoundJob, focus: string) => Promise<CoachResult>;

/**
 * Per-job coaching state: the analysis (one model call per job and focus, then reused),
 * and the user's decisions. Deciding, undoing and downloading never reach the model: the
 * accepted decisions go to a deterministic endpoint that returns the draft CV.
 * The main CV is only ever an input.
 */
export function useCoachStore(mainCv: StructuredCV | null, analyze?: Analyze) {
  const [coach, setCoach] = useState<Record<string, JobCoach>>({});
  const latest = useRef(coach);
  const cvRef = useRef(mainCv);
  cvRef.current = mainCv;
  const generation = useRef(0); // bumped when the CV changes: older answers are dropped
  const applySeq = useRef<Record<string, number>>({});

  const update = useCallback((fn: (all: Record<string, JobCoach>) => Record<string, JobCoach>) => {
    latest.current = fn(latest.current);
    setCoach(latest.current);
  }, []);
  const patch = useCallback(
    (jobId: string, fn: (c: JobCoach) => JobCoach) =>
      update((all) => ({ ...all, [jobId]: fn(all[jobId] ?? blank()) })),
    [update],
  );

  const reset = useCallback(() => {
    generation.current += 1;
    applySeq.current = {};
    update(() => ({}));
  }, [update]);

  const show = useCallback(
    (jobId: string, focus: string, result: CoachResult) =>
      patch(jobId, (c) => ({
        ...c, status: "ready", message: null, focus,
        results: { ...c.results, [focus]: result },
        drafts: { ...c.drafts, [focus]: c.drafts[focus] ?? emptyDraft() },
      })),
    [patch],
  );

  /** Ready-made suggestions (the demo); no analysis is asked for. */
  const seed = useCallback(
    (job: FoundJob, result: CoachResult) => {
      if (!latest.current[job.id]) show(job.id, AUTO_FOCUS, result);
    },
    [show],
  );

  const start = useCallback(
    async (job: FoundJob) => {
      const existing = latest.current[job.id];
      const cv = cvRef.current;
      if ((existing && existing.status !== "error") || !cv || !analyze) return; // cached or running
      const gen = generation.current;
      patch(job.id, () => blank());
      try {
        const result = await analyze(cv, job, "");
        if (gen !== generation.current) return;
        if (result.kind === "suggestions") {
          show(job.id, AUTO_FOCUS, result);
        } else {
          patch(job.id, (c) => ({ ...c, status: "choose", choice: result, message: null }));
        }
      } catch (err) {
        if (gen !== generation.current) return;
        patch(job.id, (c) => ({ ...c, status: "error", message: err instanceof Error ? err.message : "The analysis failed." }));
      }
    },
    [analyze, patch, show],
  );

  const choose = useCallback(
    async (job: FoundJob, name: string) => {
      const current = latest.current[job.id];
      const cv = cvRef.current;
      if (!current || current.status === "working" || !cv || !analyze) return;
      if (current.results[name]) {
        patch(job.id, (c) => ({ ...c, status: "ready", focus: name, message: null })); // reused
        return;
      }
      const gen = generation.current;
      patch(job.id, (c) => ({ ...c, status: "working", message: null }));
      try {
        const result = await analyze(cv, job, name);
        if (gen === generation.current) show(job.id, name, result);
      } catch (err) {
        if (gen !== generation.current) return;
        patch(job.id, (c) => ({
          ...c, status: c.choice ? "choose" : "error",
          message: err instanceof Error ? err.message : "The analysis failed.",
        }));
      }
    },
    [analyze, patch, show],
  );

  const changeFocus = useCallback(
    (job: FoundJob) => patch(job.id, (c) => (c.choice ? { ...c, status: "choose", message: null } : c)),
    [patch],
  );

  const decide = useCallback(
    async (job: FoundJob, action: DraftAction) => {
      const current = latest.current[job.id];
      const cv = cvRef.current;
      const key = current?.focus;
      if (!current || key == null || !cv) return;
      const result = current.results[key];
      const draft = nextDraft(current.drafts[key] ?? emptyDraft(), action);
      const work = hasWork(draft);
      patch(job.id, (c) => ({
        ...c,
        drafts: { ...c.drafts, [key]: { ...draft, applied: work ? draft.applied : null, applying: work, error: null } },
      }));
      if (!work) return;
      const token = (applySeq.current[`${job.id}/${key}`] = (applySeq.current[`${job.id}/${key}`] ?? 0) + 1);
      const gen = generation.current;
      try {
        const applied = await applyDecisions({
          cv, suggestions: result.suggestions, decisions: draft.decisions,
          additions: Object.values(draft.additions), job_description: job.job_description,
        });
        if (applySeq.current[`${job.id}/${key}`] !== token || gen !== generation.current) return;
        patch(job.id, (c) => ({ ...c, drafts: { ...c.drafts, [key]: { ...c.drafts[key], applied, applying: false, error: null } } }));
      } catch (err) {
        if (applySeq.current[`${job.id}/${key}`] !== token) return;
        patch(job.id, (c) => ({
          ...c,
          drafts: { ...c.drafts, [key]: { ...c.drafts[key], applying: false, error: err instanceof Error ? err.message : "Could not apply your decision." } },
        }));
      }
    },
    [patch],
  );

  return { coach, start, choose, changeFocus, decide, seed, reset };
}

export type CoachStore = ReturnType<typeof useCoachStore>;
