import type { CVBullet, CVExperience, CvChange, FoundJob, StructuredCV } from "../types";

// Synthetic candidate and jobs. Nothing here is real personal data.
const base = {
  name: "Elçin Yıldız",
  email: "elcin.yildiz@example.com",
  phone: "+90 555 000 00 00",
  location: "İstanbul, Türkiye",
  links: ["github.com/example-elcin", "linkedin.com/in/example-elcin"],
  education: [
    {
      id: "edu1",
      school: "Örnek Teknik Üniversitesi",
      degree: "B.Sc. Computer Engineering",
      start: "2014",
      end: "2018",
      details: "Graduation project: anomaly detection on sensor streams.",
    },
  ],
  certifications: [
    { id: "cert1", name: "Cloud Practitioner", issuer: "Example Cloud Academy", date: "2022" },
  ],
  languages: ["Turkish (native)", "English (C1)", "German (A2)"],
};

// One pool of source experiences; each job picks and orders its own bullets.
const pool: Record<string, { meta: Omit<CVExperience, "bullets">; bullets: Record<string, string> }> = {
  exp1: {
    meta: { id: "exp1", employer: "Boğaz Yazılım", title: "Senior Software Engineer",
      start: "2022", end: "Present", location: "İstanbul" },
    bullets: {
      b1: "Built an LLM-based invoice triage agent that routes 12,000 documents per month and cut manual review by 60%.",
      b2: "Designed workflow automations with queues and retries, replacing five hand-run scripts.",
      b3: "Trained and deployed a churn-prediction model that lifted retention campaign precision by 18%.",
      b4: "Set up evaluation dashboards and offline test sets to track model quality across releases.",
      b5: "Mentored four engineers and led the weekly architecture review.",
    },
  },
  exp2: {
    meta: { id: "exp2", employer: "Çınar Veri", title: "Data Engineer",
      start: "2018", end: "2022", location: "Ankara" },
    bullets: {
      b1: "Automated nightly ETL pipelines in Python and Airflow, saving about 20 engineer-hours per week.",
      b2: "Built a feature store serving 40 features to three production models.",
      b3: "Introduced data-quality checks that caught schema drift before it reached reports.",
      b4: "Integrated third-party APIs and webhooks into internal tools for the operations team.",
    },
  },
};

function experiences(pick: Record<string, string[]>): CVExperience[] {
  return Object.entries(pick).map(([expId, bulletIds]) => {
    const src = pool[expId];
    const bullets: CVBullet[] = bulletIds.map((b) => ({ id: `${expId}.${b}`, text: src.bullets[b] }));
    return { ...src.meta, bullets };
  });
}

const automationCv: StructuredCV = {
  ...base,
  summary:
    "Software engineer who turns manual, error-prone workflows into reliable LLM-powered automations. " +
    "Seven years of Python, APIs and data pipelines, with a focus on agents that people can trust in production.",
  experiences: experiences({ exp1: ["b1", "b2", "b5"], exp2: ["b1", "b4"] }),
  skills: ["Python", "LLM agents", "FastAPI", "Workflow automation", "Airflow", "REST APIs", "Docker"],
  projects: [
    { id: "proj1", name: "Mail-to-ticket agent",
      description: "Classifies inbound email and opens structured tickets automatically." },
  ],
};

const mlCv: StructuredCV = {
  ...base,
  summary:
    "Machine learning engineer who takes models from experiment to production. " +
    "Seven years across feature engineering, training, evaluation and serving, with a bias for measurable impact.",
  experiences: experiences({ exp1: ["b3", "b4", "b5"], exp2: ["b2", "b3"] }),
  skills: ["Python", "scikit-learn", "PyTorch", "Feature stores", "Model evaluation", "MLOps", "SQL"],
  projects: [
    { id: "proj1", name: "Sensor anomaly detector",
      description: "Streaming anomaly detection with a retraining schedule and drift alerts." },
  ],
};

/** A synthetic posting with the CV that "Tailor my CV" shows for it. */
export interface DemoJob { job: FoundJob; cv: StructuredCV; changes: CvChange[] }

/** What a candidate would have in their confirmed CV before tailoring (demo only). */
const BASE_SUMMARY =
  "Software engineer with seven years of experience in Python, APIs and data pipelines.";
const AUTOMATION_WHERE = "Senior Software Engineer — Boğaz Yazılım";
const DATA_WHERE = "Data Engineer — Çınar Veri";

const lines = (...parts: string[]) => parts.join("\n");

export const DEMO_JOBS: DemoJob[] = [
  {
    job: {
      id: "demo-automation", title: "AI Automation Engineer", company: "Northwind Labs",
      location: "İstanbul, Türkiye (Hybrid)", source_url: "", status: "ready",
      job_description: lines(
        "About the role",
        "We are looking for an AI Automation Engineer to replace manual, error-prone workflows with reliable LLM-powered automations.",
        "",
        "What you will do",
        "- Build agents that classify documents and route them to the right team",
        "- Design workflows with queues, retries and monitoring",
        "- Integrate third-party APIs and webhooks into internal tools",
        "",
        "What we are looking for",
        "- Strong Python and API experience",
        "- Experience shipping automation or LLM features to production",
      ),
    },
    cv: automationCv,
    changes: [
      { kind: "moved", id: "exp1.b5", where: AUTOMATION_WHERE, before: "",
        after: pool.exp1.bullets.b5, detail: "Moved from 5th to 3rd" },
      { kind: "moved", id: "exp2.b4", where: DATA_WHERE, before: "",
        after: pool.exp2.bullets.b4, detail: "Moved from 4th to 2nd" },
      { kind: "summary", id: "summary", where: "Summary", before: BASE_SUMMARY,
        after: automationCv.summary, detail: "" },
    ],
  },
  {
    job: {
      id: "demo-ml", title: "Machine Learning Engineer", company: "Kestrel Analytics",
      location: "Berlin, Germany (Remote)", source_url: "", status: "ready",
      job_description: lines(
        "About the role",
        "Kestrel Analytics is hiring a Machine Learning Engineer to take models from experiment to production.",
        "",
        "What you will do",
        "- Train, evaluate and monitor prediction models",
        "- Maintain feature pipelines and a feature store",
        "- Track model quality across releases with offline test sets",
        "",
        "What we are looking for",
        "- Python, scikit-learn or PyTorch",
        "- Experience with data pipelines and model evaluation",
      ),
    },
    cv: mlCv,
    changes: [
      { kind: "moved", id: "exp1.b3", where: AUTOMATION_WHERE, before: "",
        after: pool.exp1.bullets.b3, detail: "Moved from 3rd to 1st" },
      { kind: "moved", id: "exp2.b2", where: DATA_WHERE, before: "",
        after: pool.exp2.bullets.b2, detail: "Moved from 2nd to 1st" },
      { kind: "summary", id: "summary", where: "Summary", before: BASE_SUMMARY,
        after: mlCv.summary, detail: "" },
    ],
  },
];
