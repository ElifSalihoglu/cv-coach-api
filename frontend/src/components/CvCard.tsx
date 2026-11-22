import { Link } from "react-router-dom";
import { useSession } from "../session";

/** Compact "Your CV" card: upload, continue, or review, depending on how far the user got. */
export function CvCard() {
  const { session } = useSession();
  const { fileName, confirmedCv, text } = session.cv;

  return (
    <aside className="cv-card" aria-label="Your CV">
      <h2>Your CV</h2>
      {confirmedCv ? (
        <>
          <p className="cv-card-file">✓ {fileName}</p>
          <Link to="/cv" className="button">Review CV</Link>
        </>
      ) : text !== null ? (
        <>
          <p className="muted">{fileName} is not confirmed yet.</p>
          <Link to="/cv" className="button">Continue</Link>
        </>
      ) : (
        <>
          <p className="muted">Optional now. Needed when you tailor a CV to a job.</p>
          <Link to="/cv" className="button">Upload CV</Link>
        </>
      )}
    </aside>
  );
}
