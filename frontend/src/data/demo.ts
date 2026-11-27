import type { CoachResult, Posting, StructuredCV } from "../types";

/**
 * Two sample scenarios with synthetic candidates and postings; nothing here is real personal data.
 * The results are pre-recorded: they are what the real validation produced for synthetic model
 * answers, including the proposals it removed and the routing decision. No language model is called.
 */
export interface DemoScenario {
  id: string;
  label: string;
  cv: StructuredCV;
  posting: Posting;
  result: CoachResult;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    "id": "it",
    "label": "IT posting",
    "cv": {
      "name": "Elçin Yıldız",
      "email": "elcin.yildiz@example.com",
      "phone": "+90 555 000 00 00",
      "location": "İstanbul, Türkiye",
      "links": [
        "github.com/example-elcin",
        "linkedin.com/in/example-elcin"
      ],
      "summary": "Software engineer with seven years of experience in Python, APIs and data pipelines.",
      "experiences": [
        {
          "id": "exp1",
          "employer": "Boğaz Yazılım",
          "title": "Senior Software Engineer",
          "start": "2022",
          "end": "Present",
          "location": "İstanbul",
          "bullets": [
            {
              "id": "exp1.b1",
              "text": "Built an LLM-based invoice triage agent that routes 12,000 documents per month and cut manual review by 60%."
            },
            {
              "id": "exp1.b2",
              "text": "Designed workflow automations with queues and retries, replacing five hand-run scripts."
            },
            {
              "id": "exp1.b3",
              "text": "Trained and deployed a churn-prediction model that lifted retention campaign precision by 18%."
            },
            {
              "id": "exp1.b4",
              "text": "Set up evaluation dashboards and offline test sets to track model quality across releases."
            },
            {
              "id": "exp1.b5",
              "text": "Mentored four engineers and led the weekly architecture review."
            }
          ]
        },
        {
          "id": "exp2",
          "employer": "Çınar Veri",
          "title": "Data Engineer",
          "start": "2018",
          "end": "2022",
          "location": "Ankara",
          "bullets": [
            {
              "id": "exp2.b1",
              "text": "Automated nightly ETL pipelines in Python and Airflow, saving about 20 engineer-hours per week."
            },
            {
              "id": "exp2.b2",
              "text": "Built a feature store serving 40 features to three production models."
            },
            {
              "id": "exp2.b3",
              "text": "Introduced data-quality checks that caught schema drift before it reached reports."
            },
            {
              "id": "exp2.b4",
              "text": "Integrated third-party APIs and webhooks into internal tools for the operations team."
            }
          ]
        }
      ],
      "education": [
        {
          "id": "edu1",
          "school": "Örnek Teknik Üniversitesi",
          "degree": "B.Sc. Computer Engineering",
          "start": "2014",
          "end": "2018",
          "details": "Graduation project: anomaly detection on sensor streams."
        }
      ],
      "skills": [
        "Python",
        "FastAPI",
        "Airflow",
        "SQL",
        "Docker",
        "REST APIs"
      ],
      "projects": [],
      "certifications": [
        {
          "id": "cert1",
          "name": "Cloud Practitioner",
          "issuer": "Example Cloud Academy",
          "date": "2022"
        }
      ],
      "languages": [
        "Turkish (native)",
        "English (C1)",
        "German (A2)"
      ]
    },
    "posting": {
      "title": "AI Automation Engineer",
      "description": "About the role\nWe are looking for an AI Automation Engineer to replace manual, error-prone workflows with reliable LLM-powered automations.\n\nWhat you will do\n- Build agents that classify documents and route them to the right team\n- Design workflows with queues, retries and monitoring\n- Integrate third-party APIs and webhooks into internal tools\n\nWhat we are looking for\n- Strong Python and API experience\n- Experience shipping automation or LLM features to production",
      "company": "Northwind Labs"
    },
    "result": {
      "kind": "suggestions",
      "focus": "",
      "responsibilities": [
        "Build agents that classify and route documents",
        "Design reliable workflows",
        "Integrate third-party APIs and webhooks"
      ],
      "requirements": [
        {
          "text": "Strong Python and API experience",
          "quote": "Strong Python and API experience",
          "level": "required"
        },
        {
          "text": "Shipping automation or LLM features to production",
          "quote": "Experience shipping automation or LLM features to production",
          "level": "required"
        }
      ],
      "tracks": [],
      "suggestions": [
        {
          "id": "summary",
          "kind": "summary",
          "requirement": "Experience shipping automation or LLM features to production",
          "level": "required",
          "sources": [
            {
              "id": "exp1.b1",
              "where": "Senior Software Engineer — Boğaz Yazılım",
              "text": "Built an LLM-based invoice triage agent that routes 12,000 documents per month and cut manual review by 60%."
            }
          ],
          "support": "related",
          "before": "Software engineer with seven years of experience in Python, APIs and data pipelines.",
          "after": "Software engineer with seven years in Python and APIs who ships LLM-based automations to production, such as an invoice triage agent that routes 12,000 documents per month.",
          "position": null,
          "rationale": "Related experience: this line is close to the requirement but does not mention llm.",
          "priority": 1
        },
        {
          "id": "promote:exp2.b4",
          "kind": "promote",
          "requirement": "Integrate third-party APIs and webhooks into internal tools",
          "level": "required",
          "sources": [
            {
              "id": "exp2.b4",
              "where": "Data Engineer — Çınar Veri",
              "text": "Integrated third-party APIs and webhooks into internal tools for the operations team."
            }
          ],
          "support": "direct",
          "before": "Integrated third-party APIs and webhooks into internal tools for the operations team.",
          "after": "Integrated third-party APIs and webhooks into internal tools for the operations team.",
          "position": 4,
          "rationale": "The posting names this integration work; your line says exactly that.",
          "priority": 2
        }
      ],
      "questions": [
        {
          "id": "ask:monitoring",
          "requirement": "Design workflows with queues, retries and monitoring",
          "level": "required",
          "term": "monitoring",
          "text": "The posting requires monitoring. Your CV doesn't mention it. Have you used it?"
        }
      ],
      "dropped": 2,
      "dropped_reasons": {
        "rewrite_unsupported_claim": 1,
        "quote_not_in_posting": 1
      },
      "meta": {
        "routing": {
          "primary": "it",
          "method": "rules",
          "confidence": "high",
          "reasons": [
            "title_cue:ai"
          ]
        },
        "runs": [
          {
            "agent_id": "it",
            "status": "ok",
            "duration_ms": 6,
            "error_code": ""
          }
        ],
        "provenance": {
          "summary": "it",
          "promote:exp2.b4": "it",
          "ask:monitoring": "it"
        }
      }
    }
  },
  {
    "id": "nurse",
    "label": "Nursing posting",
    "cv": {
      "name": "Aylin Demir",
      "email": "aylin.demir@example.com",
      "phone": "+90 532 000 00 00",
      "location": "Izmir",
      "links": [
        "https://example.com/aylin"
      ],
      "summary": "Registered nurse with eight years of experience in medical wards and elderly care.",
      "experiences": [
        {
          "id": "exp1",
          "employer": "Anadolu Medical Centre",
          "title": "Staff Nurse",
          "start": "2019",
          "end": "Present",
          "location": "",
          "bullets": [
            {
              "id": "exp1.b1",
              "text": "Cared for 12 medical-ward patients per shift, giving medication and monitoring vital signs."
            },
            {
              "id": "exp1.b2",
              "text": "Trained 6 new nurses on the ward's handover procedure."
            },
            {
              "id": "exp1.b3",
              "text": "Reduced medication errors on the ward by 30% by introducing a double-check routine."
            },
            {
              "id": "exp1.b4",
              "text": "Coordinated discharge plans with physiotherapists and social workers."
            }
          ]
        },
        {
          "id": "exp2",
          "employer": "Marmara Care Home",
          "title": "Healthcare Assistant",
          "start": "2016",
          "end": "2019",
          "location": "",
          "bullets": [
            {
              "id": "exp2.b1",
              "text": "Supported 25 elderly residents with daily care and mobility."
            },
            {
              "id": "exp2.b2",
              "text": "Recorded care notes in the electronic patient record system."
            }
          ]
        }
      ],
      "education": [
        {
          "id": "edu1",
          "school": "Ege University",
          "degree": "BSc Nursing",
          "start": "2012",
          "end": "2016",
          "details": "Thesis on pressure-ulcer prevention (2016)"
        }
      ],
      "skills": [
        "Patient assessment",
        "Medication administration",
        "Wound care",
        "Electronic patient records"
      ],
      "projects": [],
      "certifications": [
        {
          "id": "cert1",
          "name": "Basic Life Support (BLS)",
          "issuer": "Turkish Red Crescent",
          "date": "2023"
        },
        {
          "id": "cert2",
          "name": "Registered Nurse Licence No: 123456",
          "issuer": "Ministry of Health",
          "date": "2016"
        }
      ],
      "languages": [
        "Turkish (native)",
        "English (B2)"
      ]
    },
    "posting": {
      "title": "Staff Nurse - Surgical Ward",
      "description": "Staff Nurse - Surgical Ward\n\nAbout the role\nBayview Hospital is hiring a Staff Nurse for its 30-bed surgical ward.\n\nWhat you will do\n- Provide pre- and post-operative care for surgical patients\n- Administer medication and monitor vital signs\n- Lead the ward handover and mentor new nurses\n- Record care in the electronic patient record\n\nWhat you bring\n- Registered Nurse licence (required)\n- Basic Life Support (BLS) certification\n- 3+ years of ward experience\n- Wound care experience\n\nNice to have\n- Advanced Cardiac Life Support (ACLS) certification\n- Experience with surgical drains\n",
      "company": "Bayview Hospital"
    },
    "result": {
      "kind": "suggestions",
      "focus": "",
      "responsibilities": [
        "Provide pre- and post-operative care for surgical patients",
        "Administer medication and monitor vital signs",
        "Mentor new nurses"
      ],
      "requirements": [
        {
          "text": "Registered Nurse licence",
          "quote": "Registered Nurse licence (required)",
          "level": "required"
        },
        {
          "text": "Basic Life Support (BLS) certification",
          "quote": "Basic Life Support (BLS) certification",
          "level": "required"
        },
        {
          "text": "ACLS certification",
          "quote": "Advanced Cardiac Life Support (ACLS) certification",
          "level": "preferred"
        }
      ],
      "tracks": [],
      "suggestions": [
        {
          "id": "summary",
          "kind": "summary",
          "requirement": "Administer medication and monitor vital signs",
          "level": "required",
          "sources": [
            {
              "id": "exp1.b3",
              "where": "Staff Nurse — Anadolu Medical Centre",
              "text": "Reduced medication errors on the ward by 30% by introducing a double-check routine."
            },
            {
              "id": "exp1.b2",
              "where": "Staff Nurse — Anadolu Medical Centre",
              "text": "Trained 6 new nurses on the ward's handover procedure."
            },
            {
              "id": "exp2.b1",
              "where": "Healthcare Assistant — Marmara Care Home",
              "text": "Supported 25 elderly residents with daily care and mobility."
            }
          ],
          "support": "direct",
          "before": "Registered nurse with eight years of experience in medical wards and elderly care.",
          "after": "Registered nurse with eight years in medical wards and elderly care, who reduced medication errors on a medical ward by 30% and trained 6 new nurses on its handover procedure.",
          "position": null,
          "rationale": "Leads with the measured medication-safety result.",
          "priority": 1
        },
        {
          "id": "promote:exp1.b2",
          "kind": "promote",
          "requirement": "Lead the ward handover and mentor new nurses",
          "level": "required",
          "sources": [
            {
              "id": "exp1.b2",
              "where": "Staff Nurse — Anadolu Medical Centre",
              "text": "Trained 6 new nurses on the ward's handover procedure."
            }
          ],
          "support": "related",
          "before": "Trained 6 new nurses on the ward's handover procedure.",
          "after": "Trained 6 new nurses on the ward's handover procedure.",
          "position": 2,
          "rationale": "Related: training new nurses on handover, not leading the ward handover.",
          "priority": 2
        }
      ],
      "questions": [
        {
          "id": "ask:acls",
          "requirement": "Advanced Cardiac Life Support (ACLS) certification",
          "level": "preferred",
          "term": "ACLS",
          "text": "The posting prefers ACLS. Your CV doesn't mention it. Have you used it?"
        }
      ],
      "dropped": 1,
      "dropped_reasons": {
        "years_requirement": 1
      },
      "meta": {
        "routing": {
          "primary": "general",
          "method": "fallback",
          "confidence": "low",
          "reasons": [
            "no_clear_match"
          ]
        },
        "runs": [
          {
            "agent_id": "general",
            "status": "ok",
            "duration_ms": 4,
            "error_code": ""
          }
        ],
        "provenance": {
          "summary": "general",
          "promote:exp1.b2": "general",
          "ask:acls": "general"
        }
      }
    }
  }
];
