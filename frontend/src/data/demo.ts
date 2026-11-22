import type { CoachResult, FoundJob, StructuredCV, Suggestion } from "../types";

// Synthetic candidate, postings and suggestions. Nothing here is real personal data.
const bullets = (exp: string, texts: string[]) => texts.map((text, i) => ({ id: `${exp}.b${i + 1}`, text }));

/** The candidate's confirmed main CV. Suggestions are proposals on top of it. */
export const DEMO_MAIN_CV: StructuredCV = {
  name: "Elçin Yıldız",
  email: "elcin.yildiz@example.com",
  phone: "+90 555 000 00 00",
  location: "İstanbul, Türkiye",
  links: ["github.com/example-elcin", "linkedin.com/in/example-elcin"],
  summary: "Software engineer with seven years of experience in Python, APIs and data pipelines.",
  experiences: [
    {
      id: "exp1", employer: "Boğaz Yazılım", title: "Senior Software Engineer",
      start: "2022", end: "Present", location: "İstanbul",
      bullets: bullets("exp1", [
        "Built an LLM-based invoice triage agent that routes 12,000 documents per month and cut manual review by 60%.",
        "Designed workflow automations with queues and retries, replacing five hand-run scripts.",
        "Trained and deployed a churn-prediction model that lifted retention campaign precision by 18%.",
        "Set up evaluation dashboards and offline test sets to track model quality across releases.",
        "Mentored four engineers and led the weekly architecture review.",
      ]),
    },
    {
      id: "exp2", employer: "Çınar Veri", title: "Data Engineer",
      start: "2018", end: "2022", location: "Ankara",
      bullets: bullets("exp2", [
        "Automated nightly ETL pipelines in Python and Airflow, saving about 20 engineer-hours per week.",
        "Built a feature store serving 40 features to three production models.",
        "Introduced data-quality checks that caught schema drift before it reached reports.",
        "Integrated third-party APIs and webhooks into internal tools for the operations team.",
      ]),
    },
  ],
  education: [
    {
      id: "edu1", school: "Örnek Teknik Üniversitesi", degree: "B.Sc. Computer Engineering",
      start: "2014", end: "2018", details: "Graduation project: anomaly detection on sensor streams.",
    },
  ],
  skills: ["Python", "FastAPI", "Airflow", "SQL", "Docker", "REST APIs"],
  projects: [],
  certifications: [{ id: "cert1", name: "Cloud Practitioner", issuer: "Example Cloud Academy", date: "2022" }],
  languages: ["Turkish (native)", "English (C1)", "German (A2)"],
};

const AUTOMATION_WHERE = "Senior Software Engineer — Boğaz Yazılım";
const DATA_WHERE = "Data Engineer — Çınar Veri";
const lineOf = (id: string) => {
  const [exp] = id.split(".b");
  return DEMO_MAIN_CV.experiences.find((e) => e.id === exp)!.bullets.find((b) => b.id === id)!.text;
};
const position = (id: string) => {
  const [exp] = id.split(".b");
  return DEMO_MAIN_CV.experiences.find((e) => e.id === exp)!.bullets.findIndex((b) => b.id === id) + 1;
};

function promote(id: string, where: string, requirement: string, rationale: string, priority: number): Suggestion {
  return {
    id: `promote:${id}`, kind: "promote", requirement, level: "required",
    sources: [{ id, where, text: lineOf(id) }], support: "direct",
    before: lineOf(id), after: lineOf(id), position: position(id), rationale, priority,
  };
}

function summary(after: string, sourceId: string, where: string, requirement: string, rationale: string, priority: number): Suggestion {
  return {
    id: "summary", kind: "summary", requirement, level: "required",
    sources: [{ id: sourceId, where, text: lineOf(sourceId) }], support: "direct",
    before: DEMO_MAIN_CV.summary, after, position: null, rationale, priority,
  };
}

const lines = (...parts: string[]) => parts.join("\n");

/** A synthetic posting and what the coach would propose for it (no model involved in the demo). */
export interface DemoJob { job: FoundJob; result: CoachResult }

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
    result: {
      kind: "suggestions", focus: "", dropped: 0, tracks: [],
      responsibilities: [
        "Build agents that classify and route documents",
        "Design reliable workflows",
        "Integrate third-party APIs and webhooks",
      ],
      requirements: [
        { text: "Strong Python and API experience", quote: "Strong Python and API experience", level: "required" },
        { text: "Shipping automation or LLM features to production", quote: "Experience shipping automation or LLM features to production", level: "required" },
      ],
      suggestions: [
        summary(
          "Software engineer with seven years in Python and APIs who ships LLM-based automations to production, such as an invoice triage agent that routes 12,000 documents per month.",
          "exp1.b1", AUTOMATION_WHERE, "Experience shipping automation or LLM features to production",
          "Puts the production agent and its scale in the first lines.", 1,
        ),
        promote(
          "exp2.b4", DATA_WHERE, "Integrate third-party APIs and webhooks into internal tools",
          "The posting names this integration work; your line says exactly that.", 2,
        ),
      ],
      questions: [{
        id: "ask:monitoring", level: "required", term: "monitoring",
        requirement: "Design workflows with queues, retries and monitoring",
        text: "The posting requires monitoring. Your CV doesn't mention it. Have you used it?",
      }],
    },
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
    result: {
      kind: "suggestions", focus: "", dropped: 0, tracks: [],
      responsibilities: [
        "Train, evaluate and monitor prediction models",
        "Maintain feature pipelines and a feature store",
        "Track model quality across releases",
      ],
      requirements: [
        { text: "Python, scikit-learn or PyTorch", quote: "Python, scikit-learn or PyTorch", level: "required" },
        { text: "Data pipelines and model evaluation", quote: "Experience with data pipelines and model evaluation", level: "required" },
      ],
      suggestions: [
        promote(
          "exp1.b4", AUTOMATION_WHERE, "Track model quality across releases with offline test sets",
          "Your evaluation work matches this line of the posting almost word for word.", 1,
        ),
        summary(
          "Machine learning engineer who takes models from experiment to production, such as a churn-prediction model that lifted retention campaign precision by 18%.",
          "exp1.b3", AUTOMATION_WHERE, "Train, evaluate and monitor prediction models",
          "Leads with a trained and deployed model and its measured result.", 2,
        ),
        promote(
          "exp2.b2", DATA_WHERE, "Maintain feature pipelines and a feature store",
          "You built a feature store: that is the second line of the posting.", 3,
        ),
      ],
      questions: [{
        id: "ask:scikit-learn", level: "required", term: "scikit-learn",
        requirement: "Python, scikit-learn or PyTorch",
        text: "The posting requires scikit-learn. Your CV doesn't mention it. Have you used it?",
      }],
    },
  },
];
