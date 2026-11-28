import type { CoachMeta } from "../types";

const AGENT_NAMES: Record<string, string> = {
  it: "IT agent", healthcare: "Healthcare agent", hr: "HR agent", finance: "Finance agent", general: "General agent",
};
export const agentName = (id: string) => AGENT_NAMES[id] ?? id;

/** Why the checks removed a proposal, in the user's words. Keys are the API's reason codes. */
const DROP_REASONS: Record<string, string> = {
  quote_not_in_posting: "quoted a requirement that is not in the posting",
  source_not_in_cv: "pointed at a CV line that does not exist",
  requirement_quote_not_in_posting: "listed a requirement that is not in the posting",
  track_not_in_posting: "named a track the posting does not offer",
  evidence_not_in_cv: "cited evidence that is not in your CV",
  generic_requirement: "aimed at a generic condition (years, communication, ownership)",
  years_requirement: "aimed at a years-of-experience condition",
  already_first: "moved a line that is already first",
  rewrite_not_substantive: "reworded a line without adding anything real",
  rewrite_unsupported_claim: "reworded a line with a claim your CV does not support",
  rewrite_unlisted_qualification: "reworded a line with a qualification your CV does not list",
  summary_not_new: "proposed the summary you already have",
  summary_unsupported_claim: "wrote a summary with a claim your CV does not support",
  summary_unsupported_action: "wrote a summary with work your CV does not show",
  summary_unlisted_qualification: "wrote a summary with a qualification your CV does not list",
  question_not_grounded: "asked about something the posting does not mention",
  too_many_questions: "asked more questions than are useful",
  over_limit_or_duplicate: "was a duplicate or beyond the limit of suggestions",
  unknown_kind: "was a kind of suggestion we do not support",
};

function routingText(meta: CoachMeta): string[] {
  const { routing } = meta;
  const lines: string[] = [];
  const failed = routing.reasons.filter((r) => r.startsWith("agent_failed:")).map((r) => agentName(r.split(":")[1]));
  const called = routing.reasons.filter((r) => r.startsWith("delegated:")).map((r) => agentName(r.split(":")[1]));
  if (failed.length) {
    lines.push(`The ${failed.join(" and the ")} could not finish, so the ${agentName(routing.primary)} answered instead.`);
  } else if (routing.method === "override") {
    lines.push("You chose this agent.");
  } else if (routing.method === "delegation" && called.length > 1) {
    lines.push(`The General agent called the ${called.join(" and the ")} and combined their results.`);
  } else if (routing.method === "delegation") {
    lines.push(`The General agent handed this posting to the ${agentName(routing.primary)}.`);
  } else {
    lines.push("No specialist agent clearly matched this posting, so the General agent analysed it.");
  }
  return lines;
}

interface Props {
  meta: CoachMeta | null;
  dropped: number;
  droppedReasons: Record<string, number>;
}

/** Which agent answered and why, and what the validation removed. Shown above the suggestions. */
export function AgentPanel({ meta, dropped, droppedReasons }: Props) {
  return (
    <section className="agent-panel" aria-label="How this analysis was made">
      {meta && (
        <p className="agent-line">
          <span className="tag">Answered by</span> <strong>{agentName(meta.routing.primary)}</strong>
          <span className="muted"> · {routingText(meta).join(" ")}</span>
        </p>
      )}
      {meta && meta.runs.length > 0 && (
        <p className="agent-line" aria-label="Agents called">
          <span className="tag">Called</span>{" "}
          {meta.runs.map((run, i) => (
            <span key={`${run.agent_id}-${i}`} className={run.status === "ok" ? "" : "muted"}>
              {i > 0 && " · "}
              {agentName(run.agent_id)}
              {run.status === "ok" ? "" : " (failed)"}
            </span>
          ))}
        </p>
      )}
      <p className="agent-line">
        <span className="tag">Checks</span>{" "}
        {dropped === 0 ? (
          <span>Every proposal from the model passed our checks.</span>
        ) : (
          <span>
            Our checks removed <strong>{dropped}</strong> {dropped === 1 ? "proposal" : "proposals"} from the
            model before you saw them.
          </span>
        )}
      </p>
      {dropped > 0 && (
        <details className="agent-checks">
          <summary>Why they were removed</summary>
          <ul>
            {Object.entries(droppedReasons).map(([code, count]) => (
              <li key={code}>
                {count} × {DROP_REASONS[code] ?? code}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
