import { useCallback, useRef, useState } from "react";

export default function ErrorText({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return <div className="error-text">{error}</div>;
}

/** Wraps an async action: returns [run, busy, error, setError]. run resolves true on success. */
export function useAction<A extends unknown[]>(
  fn: (...args: A) => Promise<unknown>,
): [(...args: A) => Promise<boolean>, boolean, string | null, (e: string | null) => void] {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(async (...args: A) => {
    setBusy(true);
    setError(null);
    try {
      await fnRef.current(...args);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);
  return [run, busy, error, setError];
}
