import { useEffect, useState } from "react";

/** True while the viewport matches the media query (false where matchMedia is missing). */
export function useMediaQuery(query: string): boolean {
  const get = () => (typeof window.matchMedia === "function" ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    onChange();
    list.addEventListener?.("change", onChange);
    return () => list.removeEventListener?.("change", onChange);
  }, [query]);
  return matches;
}

export const MOBILE_QUERY = "(max-width: 800px)";
