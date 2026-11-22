import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "./App";
import type { FoundJob, StructuredCV } from "./types";

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export const renderApp = (path = "/") =>
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

export const MY_CV: StructuredCV = {
  name: "Kerem Aydın", email: "kerem@example.com", phone: "", location: "Ankara", links: [],
  summary: "Backend developer who ships reliable services.",
  experiences: [{ id: "exp1", employer: "Test A.Ş.", title: "Developer", start: "2020", end: "2024",
    location: "", bullets: [{ id: "exp1.b1", text: "Built a billing API." }] }],
  education: [], skills: ["Python"], projects: [], certifications: [], languages: [],
};

export const JOB_A: FoundJob = {
  id: "indeed:aaa", title: "AI Engineer", company: "Acme", location: "Berlin",
  source_url: "https://de.indeed.com/viewjob?jk=aaa", status: "ready",
  job_description: "Acme builds agents.\nYou will ship LLM features.",
};
export const JOB_B: FoundJob = {
  id: "indeed:bbb", title: "ML Engineer", company: "Beta", location: "Remote",
  source_url: "https://de.indeed.com/viewjob?jk=bbb", status: "ready",
  job_description: "Beta trains ranking models.",
};

/** A fake API behind `fetch`; every call is recorded so tests can count model calls. */
export function fakeApi() {
  const fetchMock = vi.fn();
  const queues: Record<string, Array<() => Promise<Response> | Response>> = {};
  const defaults: Record<string, (body: any) => Response> = {
    "/v1/cv/extract-text": () => json({ filename: "cv.txt", text: "Kerem Aydın\nBackend developer" }),
    "/v1/cv/parse": () => json({ cv: MY_CV, warnings: [] }),
    "/v1/jobs/search": () => json({ jobs: [JOB_A, JOB_B] }),
    "/v1/cv/tailor": (body) => {
      const summary = `Tailored for ${body.job_title}.`;
      return json({
        cv: { ...MY_CV, summary },
        warnings: [],
        changes: [{ kind: "summary", id: "summary", where: "Summary", before: MY_CV.summary, after: summary, detail: "" }],
      });
    },
    "/v1/cv/render-pdf": () => new Response(new Blob(["%PDF"]), { status: 200 }),
  };
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    const next = queues[url]?.shift();
    if (next) return next();
    const handler = defaults[url];
    if (!handler) throw new Error(`unexpected request ${url}`);
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    return handler(body);
  });
  return {
    fetchMock,
    /** Answer the next request to `url` with `reply` instead of the default. */
    once: (url: string, reply: () => Promise<Response> | Response) => {
      (queues[url] ??= []).push(reply);
    },
    calls: (url: string) => fetchMock.mock.calls.filter((c) => c[0] === url),
    body: (url: string, index = 0) => JSON.parse(fetchMock.mock.calls.filter((c) => c[0] === url)[index][1].body),
  };
}

export function setMobile(mobile: boolean) {
  if (!mobile) {
    // @ts-expect-error jsdom has no matchMedia; removing it means "desktop"
    delete window.matchMedia;
    return;
  }
  window.matchMedia = ((query: string) => ({
    matches: true, media: query, addEventListener() {}, removeEventListener() {},
  })) as unknown as typeof window.matchMedia;
}
