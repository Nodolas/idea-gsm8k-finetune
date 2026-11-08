import { useEffect, useRef, useState } from "react";

import { toApiError, type ApiError } from "@/lib/api";

export type PolledState<T> =
  { state: "loading" } | { state: "ready"; data: T } | { state: "error"; error: ApiError };

export const POLL_MS = 2000;

interface Held<T> {
  key: string;
  value: PolledState<T>;
}

/**
 * Reads `load` when `key` or `tick` changes and, while `again(answer)` is true, every 2 seconds
 * after. A new `key` starts from loading; a new `tick` keeps the last answer on screen. A failed
 * poll keeps the last good answer.
 */
export function usePolled<T>(
  load: () => Promise<T>,
  again: (data: T) => boolean,
  key: string,
  tick: number,
): PolledState<T> {
  const [held, setHeld] = useState<Held<T>>({ key, value: { state: "loading" } });
  const loadRef = useRef(load);
  const againRef = useRef(again);
  useEffect(() => {
    loadRef.current = load;
    againRef.current = again;
  });

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = () => {
      loadRef.current().then(
        (data) => {
          if (!alive) return;
          setHeld({ key, value: { state: "ready", data } });
          if (againRef.current(data)) timer = setTimeout(run, POLL_MS);
        },
        (error: unknown) => {
          if (!alive) return;
          setHeld((prev) =>
            prev.key === key && prev.value.state === "ready"
              ? prev
              : { key, value: { state: "error", error: toApiError(error) } },
          );
        },
      );
    };
    run();
    return () => {
      alive = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [key, tick]);

  return held.key === key ? held.value : { state: "loading" };
}
