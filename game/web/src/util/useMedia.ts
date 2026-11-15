import { useEffect, useState } from "react";

/** Phone layout breakpoint (matches the CSS in m3.css). */
export const MOBILE_QUERY = "(max-width: 760px)";

export function useMediaQuery(query: string): boolean {
  const get = () => typeof window !== "undefined" && window.matchMedia(query).matches;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

export const useIsMobile = () => useMediaQuery(MOBILE_QUERY);
