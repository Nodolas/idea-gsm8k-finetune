/**
 * The "GPU" panel of the training page (AC4.5.10, US4.5): the NVIDIA GPU's name, utilisation,
 * memory, temperature, power and clock from `GET /gpu`, read when the page opens and again every
 * 3 seconds until it is left. When the card cannot be read (no nvidia-smi, or the call fails) the
 * panel says "GPU stats unavailable: <reason>" and keeps trying; the rest of the page is unaffected.
 */
import { useEffect, useState } from "react";

import { StatList } from "@/components/live-numbers";
import { toApiError, type Gpu } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { gpuStats } from "@/lib/live-stats";

const REFRESH_MS = 3000;

type Reading =
  | { kind: "loading" }
  | { kind: "ready"; gpu: Gpu }
  | { kind: "unavailable"; reason: string | null };

export function GpuPanel() {
  const api = useApi();
  const [reading, setReading] = useState<Reading>({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    const read = () => {
      api.getGpu().then(
        (gpu) => {
          if (!alive) return;
          setReading(
            gpu.available ? { kind: "ready", gpu } : { kind: "unavailable", reason: gpu.reason },
          );
        },
        (error: unknown) => {
          if (alive) setReading({ kind: "unavailable", reason: toApiError(error).message });
        },
      );
    };
    read();
    const timer = setInterval(read, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [api]);

  let body;
  if (reading.kind === "loading") {
    body = <p className="text-ink-muted">Reading the GPU…</p>;
  } else if (reading.kind === "unavailable") {
    body = (
      <p className="text-ink-muted">
        {reading.reason ? `GPU stats unavailable: ${reading.reason}` : "GPU stats unavailable"}
      </p>
    );
  } else {
    body = (
      <>
        {reading.gpu.name ? (
          <p data-part="name" className="num text-sm font-semibold">
            {reading.gpu.name}
          </p>
        ) : null}
        <StatList stats={gpuStats(reading.gpu)} />
      </>
    );
  }

  return (
    <section
      aria-labelledby="gpu-heading"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-hairline bg-panel p-4"
    >
      <h2 id="gpu-heading" className="label-caps">
        GPU
      </h2>
      {body}
    </section>
  );
}
