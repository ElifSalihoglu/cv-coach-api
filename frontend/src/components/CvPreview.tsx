import type { StructuredCV } from "../types";

const dates = (a: string, b: string) => [a, b].filter(Boolean).join(" – ");
const join = (parts: string[], sep: string) => parts.filter(Boolean).join(sep);

/** `changedIds`: "summary" and bullet ids to highlight as changed for this job. */
export function CvPreview({ cv, changedIds }: { cv: StructuredCV; changedIds?: ReadonlySet<string> }) {
  const changed = (id: string) => changedIds?.has(id) ?? false;
  const mark = (id: string) => (changed(id) ? <span className="sr-only"> (changed)</span> : null);
  const contact = join([cv.email, cv.phone, cv.location, ...cv.links], " | ");
  return (
    <article className="cv-sheet" aria-label="CV preview">
      <h2 className="cv-name">{cv.name}</h2>
      {contact && <p className="cv-contact">{contact}</p>}

      {cv.summary && (
        <section>
          <h3>Summary</h3>
          <p data-testid="cv-summary" className={changed("summary") ? "is-changed" : undefined}>{cv.summary}{mark("summary")}</p>
        </section>
      )}

      {cv.experiences.length > 0 && (
        <section>
          <h3>Experience</h3>
          {cv.experiences.map((exp) => (
            <div className="cv-item" key={exp.id}>
              <p className="cv-item-title">{join([exp.title, exp.employer], " — ")}</p>
              <p className="cv-meta">{join([dates(exp.start, exp.end), exp.location], " | ")}</p>
              <ul>
                {exp.bullets.map((b) => (
                  <li key={b.id} className={changed(b.id) ? "is-changed" : undefined}>{b.text}{mark(b.id)}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      {cv.projects.length > 0 && (
        <section>
          <h3>Projects</h3>
          {cv.projects.map((p) => (
            <div className="cv-item" key={p.id}>
              <p className="cv-item-title">{p.name}</p>
              <p>{p.description}</p>
            </div>
          ))}
        </section>
      )}

      {cv.education.length > 0 && (
        <section>
          <h3>Education</h3>
          {cv.education.map((e) => (
            <div className="cv-item" key={e.id}>
              <p className="cv-item-title">{join([e.degree, e.school], " — ")}</p>
              <p className="cv-meta">{dates(e.start, e.end)}</p>
              {e.details && <p>{e.details}</p>}
            </div>
          ))}
        </section>
      )}

      {cv.certifications.length > 0 && (
        <section>
          <h3>Certifications</h3>
          <ul>
            {cv.certifications.map((c) => (
              <li key={c.id}>{join([c.name, c.issuer, c.date], " — ")}</li>
            ))}
          </ul>
        </section>
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
