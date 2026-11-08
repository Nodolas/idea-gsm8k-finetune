/**
 * The "Recent steps" table of the training page (AC4.5.8, US4.5): the ten newest logging steps of
 * the viewed run, newest first, with step, loss, learning rate, gradient norm and elapsed time.
 * Lines that only carry a dev accuracy are not steps and stay out. A value a line does not carry
 * reads "—".
 */
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { MetricsLine } from "@/lib/api";
import { fmt2, fmt3, formatElapsed, formatRate, recentStepLines } from "@/lib/live-stats";

export interface RecentStepsProps {
  /** The viewed run's lines, oldest first; the panel is only shown with at least one. */
  lines: readonly MetricsLine[];
}

export function RecentSteps({ lines }: RecentStepsProps) {
  const steps = recentStepLines(lines);
  return (
    <section aria-labelledby="recent-steps-heading" className="flex min-w-0 flex-col gap-3">
      <h2 id="recent-steps-heading" className="label-caps">
        Recent steps
      </h2>
      <Table className="num">
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="text-right">
              Step
            </TableHead>
            <TableHead scope="col" className="text-right">
              Loss
            </TableHead>
            <TableHead scope="col" className="text-right">
              Learning rate
            </TableHead>
            <TableHead scope="col" className="text-right">
              Grad norm
            </TableHead>
            <TableHead scope="col" className="text-right">
              Elapsed
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {steps.map((line) => (
            <TableRow key={`${line.step}:${line.elapsed_s}`} data-step={line.step}>
              <TableCell className="text-right">{line.step}</TableCell>
              <TableCell className="text-right">{fmt3(line.loss)}</TableCell>
              <TableCell className="text-right">{formatRate(line.learning_rate)}</TableCell>
              <TableCell className="text-right">{fmt2(line.grad_norm)}</TableCell>
              <TableCell className="text-right">{formatElapsed(line.elapsed_s)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
