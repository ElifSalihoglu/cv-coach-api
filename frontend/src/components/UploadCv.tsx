import { useRef, useState, type DragEvent } from "react";
import { errorMessage, extractCvText } from "../api";

export const SUPPORTED = [".pdf", ".docx", ".txt"];
export const MAX_MB = 5;

function validate(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED.some((ext) => name.endsWith(ext))) {
    return "Unsupported file type. Upload a PDF, DOCX or TXT file.";
  }
  if (file.size > MAX_MB * 1024 * 1024) return `This file is larger than ${MAX_MB} MB.`;
  return null;
}

/** File picker / drop area. Reads the text on the server (no model) and hands it on. */
export function UploadCv({ onExtracted }: { onExtracted: (fileName: string, text: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handle(file: File | undefined) {
    if (!file) return;
    const problem = validate(file);
    if (problem) { setError(problem); return; }
    setError(null);
    setBusy(true);
    try {
      onExtracted(file.name, await extractCvText(file));
    } catch (err) {
      setError(errorMessage(err, "Could not read this file."));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = ""; // allow picking the same file again
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    void handle(event.dataTransfer.files[0]);
  }

  return (
    <div>
      <label
        className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-busy" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={SUPPORTED.join(",")}
          disabled={busy}
          onChange={(e) => void handle(e.target.files?.[0])}
        />
        <span className="dropzone-title">{busy ? "Reading your CV…" : "Upload your CV"}</span>
        <span className="dropzone-hint">Click to choose a file, or drop it here</span>
      </label>
      <p className="supported">Supported files: PDF, DOCX, TXT (up to {MAX_MB} MB)</p>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
