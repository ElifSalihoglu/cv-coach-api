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

/** A job posting from POST /v1/jobs/search (or a demo job). */
export interface FoundJob {
  id: string;
  title: string;
  company: string;
  location: string;
  /** Link to the original posting; empty for demo jobs. */
  source_url: string;
  job_description: string;
  /** "missing_description" when the posting text could not be read. */
  status: "ready" | "missing_description";
}

/** What the PDF endpoint needs: the CV to print and the job it was made for. */
export interface PdfSource { cv: StructuredCV; company: string; title: string }

/** Progress of "Tailor my CV" for one job. */
export type TailorState =
  | { status: "working" }
  | { status: "ready"; cv: StructuredCV; warnings: string[] }
  | { status: "error"; message: string };
