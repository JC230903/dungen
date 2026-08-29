import { useCallback, useEffect, useRef, useState } from "react";

// UI preferences (sidebar width, collapsed, last-open tab) belong to the person
// at this browser, not to the diagram — so they live in localStorage rather than
// on the server. Every access is guarded: localStorage throws outright in some
// privacy modes, and a value written by an older build can fail to parse.
function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function usePersistentState<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => read(key, fallback));

  // Writing on every keystroke of a drag would thrash localStorage, so the write
  // is deferred a tick — the in-memory value stays authoritative for rendering.
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      try {
        window.localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* quota exceeded or storage disabled — the session still works, it just won't persist */
      }
    }, 150);
    return () => window.clearTimeout(timer.current);
  }, [key, value]);

  return [value, setValue] as const;
}

export function useToggle(key: string, fallback: boolean) {
  const [value, setValue] = usePersistentState(key, fallback);
  const toggle = useCallback(() => setValue((v) => !v), [setValue]);
  return [value, toggle, setValue] as const;
}
