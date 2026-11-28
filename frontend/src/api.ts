import type {
  Addition, AppliedCv, Claim, CoachResult, Decision, PdfSource, Posting, StructuredCV, Suggestion,
} from "./types";

export interface PdfDownload { blob: Blob; filename: string }

/** An API failure with a message that is safe to show. */
export class ApiError extends Error {}

const NETWORK_MESSAGE = "Could not reach the API. Check that it is running and try again.";

async function request(input: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    throw new ApiError(NETWORK_MESSAGE);
  }
  if (response.ok) return response;
  let detail: unknown = null;
  try { detail = (await response.json())?.detail; } catch { /* not JSON */ }
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    throw new ApiError((detail as { message: string }).message);
  }
  if (typeof detail === "string" && detail) throw new ApiError(detail);
  throw new ApiError(`The API returned an error (${response.status}).`);
}

export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** Read the file name from Content-Disposition, preferring the UTF-8 form. */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) {
    try { return decodeURIComponent(utf8[1].trim()); } catch { /* fall through */ }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1] : fallback;
}

/** Ask the API to render exactly this CV as a PDF. No model is involved. */
export async function fetchCvPdf({ cv, company, title }: PdfSource): Promise<PdfDownload> {
  const response = await request("/v1/cv/render-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv, company, job_title: title }),
  });
  const blob = await response.blob();
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), "CV.pdf");
  return { blob, filename };
}

export function saveBlob({ blob, filename }: PdfDownload): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Plain text of an uploaded PDF, DOCX or TXT file. No model is involved. */
export async function extractCvText(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const response = await request("/v1/cv/extract-text", { method: "POST", body: form });
  return (await response.json()).text as string;
}

export interface ParsedCv { cv: StructuredCV; warnings: string[] }

/** Structure the reviewed text into a CV (one model call). */
export async function parseCv(cvText: string): Promise<ParsedCv> {
  const response = await request("/v1/cv/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv_text: cvText }),
  });
  const body = await response.json();
  return { cv: body.cv, warnings: body.warnings ?? [] };
}

export interface AgentOption { id: string; domain: string; description: string }

/** The agents a request may name: the registered specialists, then the General agent. */
export async function fetchAgents(): Promise<AgentOption[]> {
  const response = await request("/v1/coach/agents");
  return (await response.json()) as AgentOption[];
}

export interface AnalyzeOptions {
  posting: Posting;
  /** An agent id to force; "" lets the API choose. */
  domain: string;
  /** The position the user is aiming at; helps the API choose an agent. */
  careerGoal: string;
}

/** One model call: read the posting against the confirmed CV. Without a focus the answer
 *  is either suggestions (a clear posting) or the tracks to choose from. */
export async function analyzePosting(cv: StructuredCV, options: AnalyzeOptions, focus: string): Promise<CoachResult> {
  const { posting, domain, careerGoal } = options;
  const response = await request("/v1/coach/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cv, job_title: posting.title, job_description: posting.description, focus,
      domain, career_goal: careerGoal,
    }),
  });
  return (await response.json()) as CoachResult;
}

/** The main CV with the accepted suggestions applied. No model call. */
export async function applyDecisions(payload: {
  cv: StructuredCV; suggestions: Suggestion[]; decisions: Record<string, Decision>;
  additions: Addition[]; job_description: string;
}): Promise<AppliedCv> {
  const response = await request("/v1/coach/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as AppliedCv;
}

/** What a text the user wrote says that their CV does not. No model call. */
export async function checkText(payload: {
  cv: StructuredCV; job_description: string; kind: "rewrite" | "summary" | "add";
  source_id?: string; text: string;
}): Promise<{ claims: Claim[]; message: string }> {
  const response = await request("/v1/coach/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as { claims: Claim[]; message: string };
}
