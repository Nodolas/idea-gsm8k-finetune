import type { LabVariantResult } from "@/lib/api";
import { loss3, pct0 } from "@/lib/lab-verdicts";

const DASH = "–";

function num(value: number | null | undefined, digits: number): string {
  return value === null || value === undefined ? DASH : value.toFixed(digits);
}

/** The results table: one row per variant; lesson l12 adds the time and padding columns. */
export function ResultsTable({
  lessonId,
  results,
}: {
  lessonId: string;
  results: LabVariantResult[];
}) {
  const timing = lessonId === "l12";
  const heads = [
    "Trainable weights",
    "Steps",
    "Minutes",
    "Seconds per step",
    "Last training loss",
    "Dev loss before",
    "Dev loss after",
    "Dev loss best",
    "Format rate before",
    "Format rate after",
    "Accuracy before",
    "Accuracy after",
    ...(timing ? ["Tokenize seconds", "Re-tokenize seconds per step", "Padding"] : []),
  ];
  return (
    <div className="overflow-x-auto">
      <table className="num w-full border-collapse text-left text-sm">
        <caption className="sr-only">Results per variant</caption>
        <thead>
          <tr className="border-b-[0.5px] border-hairline text-xs text-ink-muted">
            <th scope="col" className="py-2 pr-4 font-normal">
              Variant
            </th>
            {heads.map((h) => (
              <th key={h} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => {
            const s = r.summary;
            return (
              <tr key={r.name} className="border-b-[0.5px] border-hairline">
                <th scope="row" className="py-2 pr-4 font-normal whitespace-nowrap">
                  {r.label}{" "}
                </th>
                {s === null ? (
                  <td colSpan={heads.length} className="py-2 text-ink-muted">
                    Not finished yet
                  </td>
                ) : (
                  <>
                    <td className="py-2 pr-4">{s.trainable_params.toLocaleString("en-US")} </td>
                    <td className="py-2 pr-4">{s.steps} </td>
                    <td className="py-2 pr-4">{num(s.seconds / 60, 1)} </td>
                    <td className="py-2 pr-4">{num(s.seconds_per_step, 2)} </td>
                    <td className="py-2 pr-4">{loss3(s.train_loss_last)} </td>
                    <td className="py-2 pr-4">{loss3(s.dev_loss_before)} </td>
                    <td className="py-2 pr-4">{loss3(s.dev_loss_after)} </td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {loss3(s.dev_loss_best)}
                      {s.dev_loss_best_step !== null && ` (step ${s.dev_loss_best_step})`}{" "}
                    </td>
                    <td className="py-2 pr-4">{pct0(s.format_rate_before)} </td>
                    <td className="py-2 pr-4">{pct0(s.format_rate_after)} </td>
                    <td className="py-2 pr-4">{pct0(s.accuracy_before)} </td>
                    <td className="py-2 pr-4">{pct0(s.accuracy_after)} </td>
                    {timing && (
                      <>
                        <td className="py-2 pr-4">{num(s.tokenize_seconds, 2)} </td>
                        <td className="py-2 pr-4">{num(s.retokenize_seconds_per_step, 2)} </td>
                        <td className="py-2 pr-4">{pct0(s.padding_fraction)} </td>
                      </>
                    )}
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
