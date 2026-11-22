import type { CoachResult, FocusOption } from "../types";

interface Props {
  choice: CoachResult;
  message: string | null;
  onChoose: (name: string) => void;
}

function Track({ track, onChoose }: { track: FocusOption; onChoose: (name: string) => void }) {
  return (
    <li className="track">
      <div className="track-head">
        <strong>{track.name}</strong>
        <button type="button" className="primary" aria-label={`Choose ${track.name}`} onClick={() => onChoose(track.name)}>
          Choose this focus
        </button>
      </div>
      <p className="muted">{track.summary}</p>
      {track.evidence.length > 0 ? (
        <ul className="track-evidence">
          {track.evidence.map((e) => (
            <li key={e.source_id}>
              <span className="muted">{e.where}:</span> “{e.text}”
              {e.why && <span className="muted"> — {e.why}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{track.note}</p>
      )}
    </li>
  );
}

/** The posting has several tracks: the ones the CV backs up first, the rest still one click away. */
export function FocusPicker({ choice, message, onChoose }: Props) {
  const strong = choice.tracks.filter((t) => t.coverage === "strong");
  const lead = strong.length > 0 ? strong : choice.tracks.filter((t) => t.coverage === "partial");
  const others = choice.tracks.filter((t) => !lead.includes(t));
  return (
    <div className="focus-picker">
      <h4>This posting has several tracks. Which one are you applying for?</h4>
      {message && <p className="error" role="alert">{message}</p>}
      <ul className="tracks" aria-label="Tracks backed by your CV">
        {lead.map((t) => <Track key={t.id} track={t} onChoose={onChoose} />)}
      </ul>
      {others.length > 0 && (
        <details className="other-tracks">
          <summary>Other tracks in this posting ({others.length})</summary>
          <ul className="tracks">
            {others.map((t) => <Track key={t.id} track={t} onChoose={onChoose} />)}
          </ul>
        </details>
      )}
    </div>
  );
}
