import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toApiError, type CourseArchitecture, type CourseArchitectures } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { formatMillions, shortRevision } from "@/lib/course";

const PARTS = ["embeddings", "attention", "mlp", "norms", "head"] as const;
const PART_LABELS: Record<(typeof PARTS)[number], string> = {
  embeddings: "Embeddings",
  attention: "Attention",
  mlp: "MLP",
  norms: "Norms",
  head: "Output head",
};
const SEGMENT_CLASSES: Record<(typeof PARTS)[number], string> = {
  embeddings: "bg-orange",
  attention: "bg-ink",
  mlp: "bg-ink-muted",
  norms: "bg-ok",
  head: "bg-danger",
};

/** The offer to read the model designs, before architectures.json exists (AC12.5.5). */
export function ReadDesigns({ stepId, onStarted }: { stepId: string; onStarted(): void }) {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    setError(null);
    setBusy(true);
    try {
      await api.runCourseStep(stepId);
      onStarted();
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="max-w-[75ch] text-sm text-ink-muted">
        The model designs have not been read yet. Reading them takes a moment on the CPU and does
        not touch the GPU.
      </p>
      <Button disabled={busy} onClick={() => void start()}>
        Read the model designs (CPU, under a minute)
      </Button>
      {error ? (
        <p role="alert" className="max-w-[75ch] text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** c02: the sample problem's first tokens as chips and the token counts, per model. */
export function TokensView({ data }: { data: CourseArchitectures }) {
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="num text-xs text-ink-muted">{`Sample problem ${data.sample_problem_id}`}</p>
      <ul className="grid list-none gap-3 lg:grid-cols-2">
        {data.models.map((model) => (
          <li
            key={model.id}
            data-model={model.id}
            className="flex min-w-0 flex-col gap-2 rounded-sm border-[0.5px] border-hairline bg-panel p-3 text-sm"
          >
            <span className="num break-all text-ink">{model.id}</span>
            <ul
              aria-label={`First tokens of the problem for ${model.id}`}
              className="flex list-none flex-wrap gap-1"
            >
              {model.first_tokens.map((token, i) => (
                <li
                  key={i}
                  data-token-chip=""
                  className="num rounded-sm border-[0.5px] border-hairline px-1.5 py-0.5 text-xs whitespace-pre text-ink"
                >
                  {token}{" "}
                </li>
              ))}
            </ul>
            <p className="num text-ink-muted">
              <span>{`${model.problem_tokens} tokens in the problem`}</span>
              <span>{"; "}</span>
              <span>{`${model.prompt_tokens} tokens in the 4-shot prompt`}</span>
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The model whose weights c03 draws: Qwen3-0.6B, else the first with that size, else the first. */
function pickSmallModel(models: CourseArchitecture[]): CourseArchitecture | null {
  return (
    models.find((m) => /Qwen3-0\.6B/.test(m.id)) ??
    models.find((m) => /0\.6B/.test(m.id)) ??
    models[0] ??
    null
  );
}

/** c03: weights by part as one stacked bar, with the numbers in a table. */
export function WeightsView({ data }: { data: CourseArchitectures }) {
  const model = pickSmallModel(data.models);
  if (model === null) return <p className="text-ink-muted">No model designs were read.</p>;
  const total = PARTS.reduce((sum, part) => sum + model.weights_by_part[part], 0);
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="num text-sm text-ink">{`${model.id}: ${formatMillions(model.weights_total)} weights`}</p>
      <div
        data-bar="weights-by-part"
        role="img"
        aria-label={`Weights by part of ${model.id}`}
        className="flex h-6 w-full overflow-hidden rounded-sm border-[0.5px] border-hairline"
      >
        {PARTS.map((part) => (
          <div
            key={part}
            data-segment={part}
            title={PART_LABELS[part]}
            className={SEGMENT_CLASSES[part]}
            style={{ width: `${total === 0 ? 0 : (model.weights_by_part[part] * 100) / total}%` }}
          />
        ))}
      </div>
      <Table className="num">
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Part</TableHead>
            <TableHead scope="col" className="text-right">
              Weights
            </TableHead>
            <TableHead scope="col" className="text-right">
              Share
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {PARTS.map((part) => (
            <TableRow key={part}>
              <TableCell>
                <span
                  aria-hidden="true"
                  className={`mr-2 inline-block size-2 rounded-sm ${SEGMENT_CLASSES[part]}`}
                />
                {PART_LABELS[part]}
              </TableCell>
              <TableCell className="text-right">
                {formatMillions(model.weights_by_part[part])}
              </TableCell>
              <TableCell className="text-right">
                {total === 0
                  ? "--"
                  : `${((model.weights_by_part[part] * 100) / total).toFixed(1)} %`}
              </TableCell>
            </TableRow>
          ))}
          <TableRow>
            <TableCell>Total</TableCell>
            <TableCell className="text-right">{formatMillions(model.weights_total)}</TableCell>
            <TableCell className="text-right">100 %</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}

type DesignRow = [label: string, cell: (m: CourseArchitecture) => ReactNode];

const DESIGN_ROWS: DesignRow[] = [
  ["Family", (m) => m.family],
  ["Revision", (m) => shortRevision(m.revision)],
  ["Licence", (m) => m.licence],
  ["Layers", (m) => m.layers],
  ["Width", (m) => m.width],
  ["Attention", (m) => m.attention],
  ["Heads", (m) => m.heads],
  ["Key-value heads", (m) => m.kv_heads],
  ["Head size", (m) => m.head_size],
  ["MLP width", (m) => m.mlp_width],
  ["MLP matrices", (m) => `${m.mlp_matrices} (${m.mlp_matrices === 3 ? "gated" : "plain"})`],
  ["Vocabulary", (m) => m.vocab.toLocaleString("en-US")],
  ["Context (tokens)", (m) => m.context.toLocaleString("en-US")],
  ["Tied embeddings", (m) => (m.tied_embeddings ? "yes" : "no")],
  ["Position encoding", (m) => m.position_encoding],
  ["Activation", (m) => m.activation],
  ["Weights in total", (m) => formatMillions(m.weights_total)],
  ["Embeddings weights", (m) => formatMillions(m.weights_by_part.embeddings)],
  ["Attention weights", (m) => formatMillions(m.weights_by_part.attention)],
  ["MLP weights", (m) => formatMillions(m.weights_by_part.mlp)],
  ["Norms weights", (m) => formatMillions(m.weights_by_part.norms)],
  ["Head weights", (m) => formatMillions(m.weights_by_part.head)],
  ["Size in bf16 (GB)", (m) => m.bf16_gb.toFixed(2)],
  ["Size in 4-bit (GB)", (m) => m.int4_gb.toFixed(2)],
  ["Problem tokens", (m) => m.problem_tokens],
  ["Prompt tokens (4-shot)", (m) => m.prompt_tokens],
];

/** c04: the course models side by side, one column each, every C9 field one row. */
export function DesignsView({ data }: { data: CourseArchitectures }) {
  return (
    <Table className="num">
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Design</TableHead>
          {data.models.map((m) => (
            <TableHead key={m.id} scope="col">
              {m.id}{" "}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {DESIGN_ROWS.map(([label, cell]) => (
          <TableRow key={label}>
            <TableHead scope="row">{label} </TableHead>
            {data.models.map((m) => (
              <TableCell key={m.id}>{cell(m)} </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
