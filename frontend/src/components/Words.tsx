import type { Piece } from "../diff";

/** Words of a text, with the ones that differ highlighted. */
export function Words({ pieces }: { pieces: Piece[] }) {
  return (
    <>
      {pieces.map((p, i) => (
        <span key={i}>
          {i > 0 && " "}
          {p.changed ? <mark>{p.text}</mark> : p.text}
        </span>
      ))}
    </>
  );
}
