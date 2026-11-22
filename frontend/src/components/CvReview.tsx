import { useState, type FormEvent, type ReactNode } from "react";
import type { CVExperience, StructuredCV } from "../types";
import { routeWarning, type RoutedWarning, type SectionKey } from "../warnings";
import {
  CertificationsView, EducationView, ExperienceView, ProjectsView, SummaryView, contactLine,
} from "./CvPreview";

interface Props {
  cv: StructuredCV;
  warnings: string[];
  /** Sections the user already saved: their warnings are no longer shown. */
  reviewed: string[];
  editing: SectionKey | null;
  setEditing: (section: SectionKey | null) => void;
  onSave: (cv: StructuredCV, section: SectionKey) => void;
}

const splitList = (value: string) =>
  value.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

function WarningList({ items }: { items: RoutedWarning[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="section-warnings" aria-label="Worth double-checking">
      {items.map((w, i) => <li key={i}>⚠ {w.text}</li>)}
    </ul>
  );
}

/** The analysed CV as editable sections, with each parse warning shown next to its item. */
export function CvReview({ cv, warnings, reviewed, editing, setEditing, onSave }: Props) {
  const routed = warnings.map(routeWarning).filter(
    (w) => w.section === "general" || !reviewed.includes(w.section),
  );
  const forSection = (section: SectionKey) => routed.filter((w) => w.section === section);
  const itemWarnings = (section: SectionKey) => (itemId: string) => (
    <WarningList items={forSection(section).filter((w) => w.itemId === itemId)} />
  );

  function save(section: SectionKey) {
    return (next: StructuredCV) => { onSave(next, section); setEditing(null); };
  }

  const common = (id: SectionKey) => ({
    id, editing, setEditing,
    warnings: forSection(id).filter((w) => w.itemId === null),
  });

  const cancel = () => setEditing(null);
  return (
    <div className="review">
      <WarningList items={routed.filter((w) => w.section === "general")} />

      <ReviewSection {...common("contact")} title="Contact"
        view={<><p className="cv-item-title">{cv.name || "No name found."}</p>
                <p className="muted">{contactLine(cv) || "No contact details found."}</p></>}
        form={<ContactForm cv={cv} onSave={save("contact")} onCancel={cancel} />} />

      <ReviewSection {...common("summary")} title="Summary"
        view={cv.summary ? <SummaryView cv={cv} /> : <p className="muted">No summary found.</p>}
        form={<SummaryForm cv={cv} onSave={save("summary")} onCancel={cancel} />} />

      <ReviewSection {...common("experience")} title="Experience" empty={cv.experiences.length === 0}
        view={<ExperienceView cv={cv} extra={itemWarnings("experience")} />}
        form={<ExperienceForm cv={cv} onSave={save("experience")} onCancel={cancel} />} />

      <ReviewSection {...common("projects")} title="Projects" empty={cv.projects.length === 0}
        view={<ProjectsView cv={cv} extra={itemWarnings("projects")} />}
        form={<ItemsForm items={cv.projects} legend={(p, i) => p.name || `Project ${i + 1}`}
                fields={[{ key: "name", label: "Name" }, { key: "description", label: "Description", multiline: true }]}
                onSave={(projects) => save("projects")({ ...cv, projects })} onCancel={cancel} />} />

      <ReviewSection {...common("education")} title="Education" empty={cv.education.length === 0}
        view={<EducationView cv={cv} extra={itemWarnings("education")} />}
        form={<ItemsForm items={cv.education} legend={(e, i) => e.degree || e.school || `Education ${i + 1}`}
                fields={[
                  { key: "school", label: "School" }, { key: "degree", label: "Degree" },
                  { key: "start", label: "Start" }, { key: "end", label: "End" },
                  { key: "details", label: "Details", multiline: true },
                ]}
                onSave={(education) => save("education")({ ...cv, education })} onCancel={cancel} />} />

      <ReviewSection {...common("certifications")} title="Certifications" empty={cv.certifications.length === 0}
        view={<CertificationsView cv={cv} extra={itemWarnings("certifications")} />}
        form={<ItemsForm items={cv.certifications} legend={(c, i) => c.name || `Certification ${i + 1}`}
                fields={[{ key: "name", label: "Name" }, { key: "issuer", label: "Issuer" }, { key: "date", label: "Date" }]}
                onSave={(certifications) => save("certifications")({ ...cv, certifications })} onCancel={cancel} />} />

      <ReviewSection {...common("skills")} title="Skills and languages"
        view={<>
          <p><strong>Skills:</strong> {cv.skills.join(", ") || "none found"}</p>
          <p><strong>Languages:</strong> {cv.languages.join(", ") || "none found"}</p>
        </>}
        form={<SkillsForm cv={cv} onSave={save("skills")} onCancel={cancel} />} />
    </div>
  );
}

function ReviewSection({ id, title, empty, view, form, editing, setEditing, warnings }: {
  id: SectionKey; title: string; empty?: boolean; view: ReactNode; form: ReactNode;
  editing: SectionKey | null; setEditing: (section: SectionKey | null) => void; warnings: RoutedWarning[];
}) {
  const isEditing = editing === id;
  return (
    <section className="review-section" aria-labelledby={`sec-${id}`}>
      <header className="review-head">
        <h3 id={`sec-${id}`}>{title}</h3>
        {!empty && !isEditing && (
          <button type="button" aria-label={`Edit ${title}`} disabled={editing !== null}
                  onClick={() => setEditing(id)}>
            Edit
          </button>
        )}
      </header>
      <WarningList items={warnings} />
      {isEditing ? form : empty ? <p className="muted">Nothing found.</p> : view}
    </section>
  );
}

// ------------------------------------------------------------------ forms

function Field({ label, value, onChange, multiline }: {
  label: string; value: string; onChange: (value: string) => void; multiline?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {multiline
        ? <textarea rows={3} value={value} onChange={(e) => onChange(e.target.value)} />
        : <input value={value} onChange={(e) => onChange(e.target.value)} />}
    </label>
  );
}

function FormShell({ onSubmit, onCancel, children }: {
  onSubmit: () => void; onCancel: () => void; children: ReactNode;
}) {
  return (
    <form className="review-form" onSubmit={(e: FormEvent) => { e.preventDefault(); onSubmit(); }}>
      {children}
      <div className="actions">
        <button type="submit" className="primary">Save</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

interface FormProps { cv: StructuredCV; onSave: (cv: StructuredCV) => void; onCancel: () => void }

function ContactForm({ cv, onSave, onCancel }: FormProps) {
  const [d, setD] = useState({ name: cv.name, email: cv.email, phone: cv.phone, location: cv.location, links: cv.links.join(", ") });
  return (
    <FormShell onCancel={onCancel}
      onSubmit={() => onSave({ ...cv, name: d.name.trim(), email: d.email.trim(), phone: d.phone.trim(),
                               location: d.location.trim(), links: splitList(d.links) })}>
      <Field label="Name" value={d.name} onChange={(name) => setD({ ...d, name })} />
      <Field label="Email" value={d.email} onChange={(email) => setD({ ...d, email })} />
      <Field label="Phone" value={d.phone} onChange={(phone) => setD({ ...d, phone })} />
      <Field label="Location" value={d.location} onChange={(location) => setD({ ...d, location })} />
      <Field label="Links (comma separated)" value={d.links} onChange={(links) => setD({ ...d, links })} />
    </FormShell>
  );
}

function SummaryForm({ cv, onSave, onCancel }: FormProps) {
  const [summary, setSummary] = useState(cv.summary);
  return (
    <FormShell onCancel={onCancel} onSubmit={() => onSave({ ...cv, summary: summary.trim() })}>
      <Field label="Summary" multiline value={summary} onChange={setSummary} />
    </FormShell>
  );
}

function SkillsForm({ cv, onSave, onCancel }: FormProps) {
  const [skills, setSkills] = useState(cv.skills.join(", "));
  const [languages, setLanguages] = useState(cv.languages.join(", "));
  return (
    <FormShell onCancel={onCancel}
      onSubmit={() => onSave({ ...cv, skills: splitList(skills), languages: splitList(languages) })}>
      <Field label="Skills (comma separated)" value={skills} onChange={setSkills} />
      <Field label="Languages (comma separated)" value={languages} onChange={setLanguages} />
    </FormShell>
  );
}

function ItemsForm<T extends { id: string }>({ items, fields, legend, onSave, onCancel }: {
  items: T[];
  fields: { key: keyof T & string; label: string; multiline?: boolean }[];
  legend: (item: T, index: number) => string;
  onSave: (items: T[]) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(items);
  return (
    <FormShell onCancel={onCancel} onSubmit={() => onSave(draft)}>
      {draft.map((item, i) => (
        <fieldset key={item.id}>
          <legend>{legend(items[i], i)}</legend>
          {fields.map((f) => (
            <Field key={f.key} label={f.label} multiline={f.multiline} value={String(item[f.key] ?? "")}
                   onChange={(value) => setDraft(draft.map((d, j) => (j === i ? { ...d, [f.key]: value } : d)))} />
          ))}
        </fieldset>
      ))}
    </FormShell>
  );
}

/** New bullets get the next free id, so ids already used for tailoring stay stable. */
function nextBulletId(exp: CVExperience): string {
  const used = exp.bullets.map((b) => Number(b.id.split(".b")[1]) || 0);
  return `${exp.id}.b${Math.max(0, ...used) + 1}`;
}

function ExperienceForm({ cv, onSave, onCancel }: FormProps) {
  const [draft, setDraft] = useState<CVExperience[]>(cv.experiences);
  const patch = (i: number, change: Partial<CVExperience>) =>
    setDraft(draft.map((e, j) => (j === i ? { ...e, ...change } : e)));

  return (
    <FormShell onCancel={onCancel}
      onSubmit={() => onSave({
        ...cv,
        experiences: draft.map((e) => ({
          ...e, bullets: e.bullets.filter((b) => b.text.trim()).map((b) => ({ ...b, text: b.text.trim() })),
        })),
      })}>
      {draft.map((exp, i) => (
        <fieldset key={exp.id}>
          <legend>{cv.experiences[i].title || cv.experiences[i].employer || `Experience ${i + 1}`}</legend>
          <Field label="Title" value={exp.title} onChange={(title) => patch(i, { title })} />
          <Field label="Company" value={exp.employer} onChange={(employer) => patch(i, { employer })} />
          <Field label="Start" value={exp.start} onChange={(start) => patch(i, { start })} />
          <Field label="End" value={exp.end} onChange={(end) => patch(i, { end })} />
          <Field label="Location" value={exp.location} onChange={(location) => patch(i, { location })} />
          {exp.bullets.map((b, j) => (
            <div className="bullet-edit" key={b.id}>
              <Field label={`Bullet ${j + 1}`} multiline value={b.text}
                     onChange={(text) => patch(i, { bullets: exp.bullets.map((x, k) => (k === j ? { ...x, text } : x)) })} />
              <button type="button" aria-label={`Remove bullet ${j + 1}`}
                      onClick={() => patch(i, { bullets: exp.bullets.filter((_, k) => k !== j) })}>
                Remove
              </button>
            </div>
          ))}
          <button type="button"
                  onClick={() => patch(i, { bullets: [...exp.bullets, { id: nextBulletId(exp), text: "" }] })}>
            Add bullet
          </button>
        </fieldset>
      ))}
    </FormShell>
  );
}
