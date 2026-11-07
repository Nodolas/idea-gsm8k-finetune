/**
 * The training page's live state (US4.5): the service status, the run queue and every metrics
 * line seen, kept current by the C7 event stream. The stream is opened once per mount and closed
 * on unmount; a line replayed on reconnect (same run id and line number) is dropped (AC4.5.2).
 * An EventSource `error` marks the view paused until the stream opens again or the next event
 * arrives (AC4.5.3; contract C7 as changed 2026-11-07).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  toApiError,
  type ApiError,
  type MetricsLine,
  type QueueEntry,
  type Status,
} from "@/lib/api";
import { useApi } from "@/lib/api-context";

export type LinesByRun = Readonly<Record<string, readonly MetricsLine[]>>;

export interface LiveStream {
  /** The latest status: from the stream, or from `GET /status` until the stream sends one. */
  status: Status | null;
  /** Set when `GET /status` failed and no status has arrived since. */
  statusError: ApiError | null;
  queue: QueueEntry[];
  /** Every metrics line seen in this page visit, per run id, in arrival order. */
  linesByRun: LinesByRun;
  /** True from a stream drop until the stream opens again or sends an event. */
  paused: boolean;
  /** When the last stream event arrived. */
  lastUpdate: Date | null;
  /** Reads status and queue again (after a start, stop or queue change). */
  refresh(): void;
}

export function useLiveStream(): LiveStream {
  const api = useApi();
  const [status, setStatus] = useState<Status | null>(null);
  const [statusError, setStatusError] = useState<ApiError | null>(null);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [linesByRun, setLinesByRun] = useState<LinesByRun>({});
  const [paused, setPaused] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Keys "<run_id>:<line number>" already taken, so a replay after a reconnect adds nothing.
  const seen = useRef<Set<string>>(new Set());
  // Bumped by every stream event of a kind, so an older HTTP answer never overwrites it.
  const statusVersion = useRef(0);
  const queueVersion = useRef(0);

  const refresh = useCallback(() => {
    const statusAt = statusVersion.current;
    const queueAt = queueVersion.current;
    api.getStatus().then(
      (next) => {
        if (statusVersion.current !== statusAt) return;
        setStatus(next);
        setStatusError(null);
      },
      (error: unknown) => {
        if (statusVersion.current === statusAt) setStatusError(toApiError(error));
      },
    );
    api.getQueue().then(
      (entries) => {
        if (queueVersion.current === queueAt) setQueue(entries);
      },
      () => {
        // The queue list is a convenience; the status error already names an unreachable service.
      },
    );
  }, [api]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const touched = () => {
      setPaused(false);
      setLastUpdate(new Date());
    };
    const close = api.openStream({
      onMetric(line, lineNo) {
        const key = `${line.run_id}:${lineNo}`;
        if (seen.current.has(key)) {
          setPaused(false);
          return;
        }
        seen.current.add(key);
        setLinesByRun((prev) => ({ ...prev, [line.run_id]: [...(prev[line.run_id] ?? []), line] }));
        touched();
      },
      onStatus(next) {
        statusVersion.current += 1;
        setStatus(next);
        setStatusError(null);
        touched();
      },
      onQueue(entries) {
        queueVersion.current += 1;
        setQueue(entries);
        touched();
      },
      onOpen() {
        setPaused(false);
      },
      onDrop() {
        setPaused(true);
      },
    });
    return close;
  }, [api]);

  return { status, statusError, queue, linesByRun, paused, lastUpdate, refresh };
}
