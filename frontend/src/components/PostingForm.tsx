import { useEffect, useState, type FormEvent } from "react";
import { fetchAgents, type AgentOption, type AnalyzeOptions } from "../api";

/** What the form offers if the API's list of agents cannot be loaded. */
const FALLBACK_AGENTS: AgentOption[] = [{ id: "general", domain: "General career", description: "" }];

/** "" lets the General agent choose; the others force an agent by its id (the list comes from the API's registry). */
function agentChoices(agents: AgentOption[]) {
  return [
    { value: "", label: "Automatic (recommended)" },
    ...agents.map((a) => ({
      value: a.id,
      label: a.id === "general" ? "General agent (any other field)" : `${a.domain} agent`,
    })),
  ];
}

interface Props {
  disabled?: boolean;
  onSubmit: (options: AnalyzeOptions) => void;
}

/** The job posting, the optional career goal and the optional choice of agent. */
export function PostingForm({ disabled = false, onSubmit }: Props) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [careerGoal, setCareerGoal] = useState("");
  const [company, setCompany] = useState("");
  const [domain, setDomain] = useState("");
  const [agents, setAgents] = useState<AgentOption[]>(FALLBACK_AGENTS);

  useEffect(() => {
    let active = true;
    fetchAgents().then((list) => active && setAgents(list), () => {});
    return () => { active = false; };
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !description.trim()) return;
    onSubmit({
      posting: { title: title.trim(), description: description.trim(), company: company.trim() },
      domain,
      careerGoal: careerGoal.trim(),
    });
  }

  return (
    <form className="posting-form" onSubmit={submit}>
      <label className="field">
        <span>Job title</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Staff Nurse" required />
      </label>
      <label className="field">
        <span>Job posting</span>
        <textarea
          rows={12}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Paste the full text of the posting: responsibilities, requirements, nice-to-haves."
          required
        />
      </label>
      <div className="form-row">
        <label className="field">
          <span>Career goal (optional)</span>
          <input value={careerGoal} onChange={(e) => setCareerGoal(e.target.value)} placeholder="e.g. Backend developer" />
          <small className="muted">Helps the General agent choose specialists; sent to the language model with the posting, never with your CV.</small>
        </label>
        <label className="field">
          <span>Company (optional)</span>
          <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Used only in the PDF file name" />
        </label>
      </div>
      <label className="field narrow">
        <span>Agent</span>
        <select value={domain} onChange={(e) => setDomain(e.target.value)}>
          {agentChoices(agents).map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <small className="muted">Automatic lets the General agent read the posting and call up to two specialists. Pick one only to override it.</small>
      </label>
      <div className="actions">
        <button type="submit" className="primary" disabled={disabled || !title.trim() || !description.trim()}>
          Analyze posting
        </button>
        <span className="muted small">A few language-model calls (at most 8). Nothing changes in your CV until you accept it.</span>
      </div>
    </form>
  );
}
