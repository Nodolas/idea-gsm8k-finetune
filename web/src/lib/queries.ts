import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";

import {
  toApiError,
  type ApiError,
  type DialSpec,
  type Reasoning,
  type RunList,
  type Status,
} from "@/lib/api";
import { useApi } from "@/lib/api-context";

export type AsyncState<T> =
  { state: "loading" } | { state: "ready"; data: T } | { state: "error"; error: ApiError };

export type AsyncResult<T> = AsyncState<T> & { reload(): void };

type Keyed<T> = { key: number; value: AsyncState<T> };

function sameDeps(a: DependencyList, b: DependencyList): boolean {
  return a.length === b.length && a.every((item, i) => Object.is(item, b[i]));
}

/**
 * Runs `load` when the component mounts and whenever `deps` change, and gives its result as
 * loading, ready or error (every error as an ApiError). `reload()` runs it again from loading.
 * An answer that arrives after newer deps or a reload is dropped.
 */
export function useAsync<T>(load: () => Promise<T>, deps: DependencyList): AsyncResult<T> {
  const loadRef = useRef(load);
  const [request, setRequest] = useState<{ key: number; deps: DependencyList }>({ key: 0, deps });
  const [result, setResult] = useState<Keyed<T>>({ key: -1, value: { state: "loading" } });

  // New deps start a new request (state adjusted during render, as React documents).
  let current = request;
  if (!sameDeps(request.deps, deps)) {
    current = { key: request.key + 1, deps };
    setRequest(current);
  }
  const key = current.key;

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    let alive = true;
    loadRef.current().then(
      (data) => {
        if (alive) setResult({ key, value: { state: "ready", data } });
      },
      (error: unknown) => {
        if (alive) setResult({ key, value: { state: "error", error: toApiError(error) } });
      },
    );
    return () => {
      alive = false;
    };
  }, [key]);

  const reload = useCallback(() => {
    setRequest((r) => ({ key: r.key + 1, deps: r.deps }));
  }, []);

  const value: AsyncState<T> = result.key === key ? result.value : { state: "loading" };
  return { ...value, reload };
}

/** The run list (`GET /runs`). */
export function useRuns(): AsyncResult<RunList> {
  const api = useApi();
  return useAsync(() => api.listRuns(), [api]);
}

/** The finalist run ids (`GET /finalists`). */
export function useFinalists(): AsyncResult<string[]> {
  const api = useApi();
  return useAsync(() => api.getFinalists(), [api]);
}

/** The reasoning comparison (`GET /reasoning`) for one model, or the service's default. */
export function useReasoning(model?: string): AsyncResult<Reasoning> {
  const api = useApi();
  return useAsync(() => api.getReasoning(model), [api, model]);
}

/** The Training Dials table (`GET /dials`). */
export function useDials(): AsyncResult<DialSpec[]> {
  const api = useApi();
  return useAsync(() => api.getDials(), [api]);
}

/**
 * The service status (`GET /status`), read on mount and then every `pollMs` (the top bar uses
 * 5 s). A poll keeps the last answer on screen until the next one arrives; `reload()` reads now.
 */
export function useStatus(pollMs = 5000): AsyncResult<Status> {
  const api = useApi();
  const [result, setResult] = useState<AsyncState<Status>>({ state: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    const read = () => {
      api.getStatus().then(
        (data) => {
          if (alive) setResult({ state: "ready", data });
        },
        (error: unknown) => {
          if (alive) setResult({ state: "error", error: toApiError(error) });
        },
      );
    };
    read();
    const timer = pollMs > 0 ? setInterval(read, pollMs) : undefined;
    return () => {
      alive = false;
      if (timer !== undefined) clearInterval(timer);
    };
  }, [api, pollMs, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...result, reload };
}
