import type { ReactNode } from "react";
import type { StructuredCV } from "../types";

const dates = (a: string, b: string) => [a, b].filter(Boolean).join(" – ");
const join = (parts: string[], sep: string) => parts.filter(Boolean).join(sep);

export const contactLine = (cv: StructuredCV) =>
  join([cv.email, cv.phone, cv.location, ...cv.links], " | ");

type Changed = (id: string) => boolean;
const never: Changed = () => false;
const mark = (isChanged: boolean) => (isChanged ? <span className="sr-only"> (changed)</span> : null);

// ---- one view per CV section; used by the preview and by the review screen ----

export function SummaryView({ cv, changed = never }: { cv: StructuredCV; changed?: Changed }) {
  return (
    <p data-testid="cv-summary" className={changed("summary") ? "is-changed" : undefined}>
      {cv.summary}{mark(changed("summary"))}
    </p>
  );
}

export function ExperienceView({ cv, changed = never, extra }: {
  cv: StructuredCV; changed?: Changed; extra?: (itemId: string) => ReactNode;
}) {
  return (
    <>
      {cv.experiences.map((exp) => (
        <div className="cv-item" key={exp.id}>
          <p className="cv-item-title">{join([exp.title, exp.employer], " — ")}</p>
          <p className="cv-meta">{join([dates(exp.start, exp.end), exp.location], " | ")}</p>
          {extra?.(exp.id)}
          <ul>
            {exp.bullets.map((b) => (
              <li key={b.id} className={changed(b.id) ? "is-changed" : undefined}>
                {b.text}{mark(changed(b.id))}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  );
}

export function ProjectsView({ cv, extra }: { cv: StructuredCV; extra?: (itemId: string) => ReactNode }) {
  return (
    <>
      {cv.projects.map((p) => (
        <div className="cv-item" key={p.id}>
          <p className="cv-item-title">{p.name}</p>
          {extra?.(p.id)}
          <p>{p.description}</p>
        </div>
      ))}
    </>
  );
}

export function EducationView({ cv, extra }: { cv: StructuredCV; extra?: (itemId: string) => ReactNode }) {
  return (
    <>
      {cv.education.map((e) => (
        <div className="cv-item" key={e.id}>
          <p className="cv-item-title">{join([e.degree, e.school], " — ")}</p>
          <p className="cv-meta">{dates(e.start, e.end)}</p>
          {extra?.(e.id)}
          {e.details && <p>{e.details}</p>}
        </div>
      ))}
    </>
  );
}

export function CertificationsView({ cv, extra }: { cv: StructuredCV; extra?: (itemId: string) => ReactNode }) {
  return (
    <ul>
      {cv.certifications.map((c) => (
        <li key={c.id}>
          {join([c.name, c.issuer, c.date], " — ")}
          {extra?.(c.id)}
        </li>
      ))}
    </ul>
  );
}

/** `changedIds`: "summary" and bullet ids to highlight as changed for this job. */
export function CvPreview({ cv, changedIds }: { cv: StructuredCV; changedIds?: ReadonlySet<string> }) {
  const changed: Changed = (id) => changedIds?.has(id) ?? false;
  const contact = contactLine(cv);
  return (
    <article className="cv-sheet" aria-label="CV preview">
      <h2 className="cv-name">{cv.name}</h2>
      {contact && <p className="cv-contact">{contact}</p>}

      {cv.summary && (
        <section><h3>Summary</h3><SummaryView cv={cv} changed={changed} /></section>
      )}
      {cv.experiences.length > 0 && (
        <section><h3>Experience</h3><ExperienceView cv={cv} changed={changed} /></section>
      )}
      {cv.projects.length > 0 && (
        <section><h3>Projects</h3><ProjectsView cv={cv} /></section>
      )}
      {cv.education.length > 0 && (
        <section><h3>Education</h3><EducationView cv={cv} /></section>
      )}
      {cv.certifications.length > 0 && (
        <section><h3>Certifications</h3><CertificationsView cv={cv} /></section>
      )}
      {cv.skills.length > 0 && (
        <section><h3>Skills</h3><p>{cv.skills.join(", ")}</p></section>
      )}
      {cv.languages.length > 0 && (
        <section><h3>Languages</h3><p>{cv.languages.join(", ")}</p></section>
      )}
    </article>
  );
}
