import type { CvChange, FoundJob, PdfSource, StructuredCV } from "./types";

export interface PdfDownload { blob: Blob; filename: string }

/** An API failure with a message that is safe to show, and the API's error code if any. */
export class ApiError extends Error {
  code: string | null;
  status: number;
  constructor(message: string, code: string | null, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

const NETWORK_MESSAGE = "Could not reach the API. Check that it is running and try again.";

/** English text for errors the API reports with a code (its own text may be in another language). */
const CODE_MESSAGES: Record<string, string> = {
  human_verification:
    "Indeed asked for a human verification, so the search stopped. Open Indeed in your browser, complete the check, then search again.",
  search_timeout: "The job search timed out before results loaded. Please try again.",
};

async function request(input: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    throw new ApiError(NETWORK_MESSAGE, "network", 0);
  }
  if (response.ok) return response;
  let detail: unknown = null;
  try { detail = (await response.json())?.detail; } catch { /* not JSON */ }
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    const d = detail as { message: string; code?: string };
    const code = d.code ?? null;
    throw new ApiError((code && CODE_MESSAGES[code]) || d.message, code, response.status);
  }
  if (typeof detail === "string" && detail) {
    throw new ApiError(detail, null, response.status);
  }
  throw new ApiError(`The API returned an error (${response.status}).`, null, response.status);
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

export interface SearchParams { query: string; city: string }

/** Find jobs and their descriptions. No CV and no model are involved. */
export async function searchJobs(params: SearchParams): Promise<FoundJob[]> {
  const response = await request("/v1/jobs/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return (await response.json()).jobs as FoundJob[];
}

export interface TailoredCv { cv: StructuredCV; warnings: string[]; changes: CvChange[] }

/** One model call: the confirmed CV tailored to one job. */
export async function tailorCv(cv: StructuredCV, job: FoundJob): Promise<TailoredCv> {
  const response = await request("/v1/cv/tailor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv, job_title: job.title, job_description: job.job_description }),
  });
  const body = await response.json();
  return { cv: body.cv, warnings: body.warnings ?? [], changes: body.changes ?? [] };
}
