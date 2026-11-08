/**
 * The dial fields of the training page (AC4.6.1): the method choice plus the eleven dials of the
 * Training Dials table, each with a visible label above it, its allowed range as helper text and,
 * after a blur with a bad value, the message under the field. Plain controlled inputs and native
 * selects; the values and messages live in RunControls, which checks them with `checkDial`.
 *
 * Each setting that has an entry in `DIAL_INFO` also gets an "Explain <label>" button (AC4.6.8),
 * one "Explain all settings" button on top, and the panel ends with the NVIDIA GPU notes
 * (AC4.6.9). Which explanations are open is state of this panel only: it never touches a value,
 * an error or the Start button.
 */
import { ChevronDown, CircleAlert } from "lucide-react";
import { useId, useState } from "react";

import { DISCLOSURE_BUTTON_CLASS, GpuNotes } from "@/components/gpu-notes";
import { Label } from "@/components/ui/label";
import type { DialSpec } from "@/lib/api";
import { DIAL_INFO, type DialInfo } from "@/lib/dial-info";

/** The run kinds the page can start: a supervised fine-tune, or a dev evaluation of the base. */
export type RunMethod = "sft" | "base";

export const METHOD_OPTIONS: ReadonlyArray<{ value: RunMethod; label: string }> = [
  { value: "sft", label: "SFT" },
  { value: "base", label: "Evaluate on dev" },
];

/** The dials an "Evaluate on dev" run sends (model, method, split dev, seed). */
export const BASE_DIALS: ReadonlySet<string> = new Set(["model", "seed"]);

/** Whether a dial is sent for the chosen method. */
export function dialUsed(method: RunMethod, name: string): boolean {
  return method === "sft" || BASE_DIALS.has(name);
}

/** The text a field shows for a value: 0.0002 -> "0.0002", "all" -> "all". */
export function rawOf(value: string | number): string {
  return String(value);
}

const FIELD_CLASS =
  "h-9 w-full min-w-0 rounded-sm border border-input bg-transparent px-3 py-1 font-mono text-sm " +
  "tabular-nums text-foreground outline-none transition-[color,box-shadow] " +
  "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring " +
  "disabled:cursor-not-allowed disabled:opacity-50 " +
  "aria-invalid:border-destructive";

/** The explanation of a setting, or undefined when `DIAL_INFO` has none (then it gets no button). */
function infoOf(key: string): DialInfo | undefined {
  return DIAL_INFO[key];
}

export interface DialsPanelProps {
  dials: DialSpec[];
  method: RunMethod;
  /** The typed text of each dial, by name. */
  values: Record<string, string>;
  /** The message of each dial that failed its last check, by name. */
  errors: Record<string, string>;
  onMethodChange(method: RunMethod): void;
  onChange(name: string, raw: string): void;
  onBlur(name: string): void;
}

export function DialsPanel({
  dials,
  method,
  values,
  errors,
  onMethodChange,
  onChange,
  onBlur,
}: DialsPanelProps) {
  const base = useId();
  const methodId = `${base}-method`;
  const modelDial = dials.find((spec) => spec.name === "model");
  const rest = dials.filter((spec) => spec.name !== "model");

  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const explainable = ["method", ...dials.map((spec) => spec.name)].filter(
    (key) => infoOf(key) !== undefined,
  );
  const allOpen = explainable.length > 0 && explainable.every((key) => open.has(key));
  const toggle = (key: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  const toggleAll = () => setOpen(allOpen ? new Set() : new Set(explainable));

  const methodInfo = infoOf("method");
  const methodField = (
    <div className="grid gap-1.5">
      <FieldHeading
        label="Method"
        htmlFor={methodId}
        info={methodInfo}
        explanationId={`${base}-method-explain`}
        open={open.has("method")}
        onToggle={() => toggle("method")}
      />
      <select
        id={methodId}
        className={FIELD_CLASS}
        value={method}
        onChange={(event) => onMethodChange(event.target.value as RunMethod)}
      >
        {METHOD_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <fieldset className="grid gap-4">
      <legend className="sr-only">Run settings</legend>
      {explainable.length > 0 && (
        <div className="flex justify-end">
          <button type="button" className={DISCLOSURE_BUTTON_CLASS} onClick={toggleAll}>
            {allOpen ? "Hide all explanations" : "Explain all settings"}
          </button>
        </div>
      )}
      {modelDial && (
        <DialField
          key={modelDial.name}
          idBase={base}
          spec={modelDial}
          raw={values[modelDial.name] ?? rawOf(modelDial.default)}
          error={errors[modelDial.name]}
          used={dialUsed(method, modelDial.name)}
          explanationOpen={open.has(modelDial.name)}
          onToggleExplanation={() => toggle(modelDial.name)}
          onChange={onChange}
          onBlur={onBlur}
        />
      )}
      {methodField}
      {rest.map((spec) => (
        <DialField
          key={spec.name}
          idBase={base}
          spec={spec}
          raw={values[spec.name] ?? rawOf(spec.default)}
          error={errors[spec.name]}
          used={dialUsed(method, spec.name)}
          explanationOpen={open.has(spec.name)}
          onToggleExplanation={() => toggle(spec.name)}
          onChange={onChange}
          onBlur={onBlur}
        />
      ))}
      <GpuNotes />
    </fieldset>
  );
}

interface FieldHeadingProps {
  label: string;
  htmlFor: string;
  info: DialInfo | undefined;
  explanationId: string;
  open: boolean;
  onToggle(): void;
}

/** The visible label of a field, with its "Explain <label>" button and, when open, the text. */
function FieldHeading({ label, htmlFor, info, explanationId, open, onToggle }: FieldHeadingProps) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <Label htmlFor={htmlFor}>{label}</Label>
        {info && (
          // The label is part of the accessible name through a visually hidden span, not
          // `aria-label`: the field's own label query then still finds only the field.
          <button
            type="button"
            className={DISCLOSURE_BUTTON_CLASS}
            aria-expanded={open}
            aria-controls={explanationId}
            onClick={onToggle}
          >
            Explain <span className="sr-only">{label}</span>
            <ChevronDown
              aria-hidden="true"
              className="transition-transform group-aria-expanded:rotate-180"
            />
          </button>
        )}
      </div>
      {info && open && <Explanation id={explanationId} info={info} />}
    </>
  );
}

function Explanation({ id, info }: { id: string; info: DialInfo }) {
  return (
    <div
      id={id}
      className="grid gap-2 rounded-sm border border-hairline bg-panel p-3 text-xs text-muted-foreground"
    >
      <p>{info.what}</p>
      <ul className="grid list-none gap-1">
        {info.effects.map((effect) => (
          <li key={effect.label}>
            <span className="font-medium text-foreground">{effect.label}:</span> {effect.text}
          </li>
        ))}
      </ul>
      <p>
        <span className="font-medium text-foreground">Tip:</span> {info.tip}
      </p>
    </div>
  );
}

interface DialFieldProps {
  idBase: string;
  spec: DialSpec;
  raw: string;
  error: string | undefined;
  used: boolean;
  explanationOpen: boolean;
  onToggleExplanation(): void;
  onChange(name: string, raw: string): void;
  onBlur(name: string): void;
}

function DialField({
  idBase,
  spec,
  raw,
  error,
  used,
  explanationOpen,
  onToggleExplanation,
  onChange,
  onBlur,
}: DialFieldProps) {
  const id = `${idBase}-${spec.name}`;
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const shownError = used ? error : undefined;
  const describedBy = shownError ? `${helpId} ${errorId}` : helpId;
  const help = used ? spec.help : `${spec.help} · not used by Evaluate on dev`;

  return (
    <div className="grid gap-1.5">
      <FieldHeading
        label={spec.label}
        htmlFor={id}
        info={infoOf(spec.name)}
        explanationId={`${id}-explain`}
        open={explanationOpen}
        onToggle={onToggleExplanation}
      />
      {spec.kind === "select" ? (
        <select
          id={id}
          className={FIELD_CLASS}
          value={raw}
          disabled={!used}
          aria-describedby={describedBy}
          aria-invalid={shownError ? true : undefined}
          onChange={(event) => onChange(spec.name, event.target.value)}
          onBlur={() => onBlur(spec.name)}
        >
          {(spec.options ?? []).map((option) => (
            <option key={String(option)} value={String(option)}>
              {String(option)}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type="text"
          inputMode={spec.kind === "integer" && !spec.allow_all ? "numeric" : "decimal"}
          autoComplete="off"
          spellCheck={false}
          className={FIELD_CLASS}
          value={raw}
          disabled={!used}
          aria-describedby={describedBy}
          aria-invalid={shownError ? true : undefined}
          onChange={(event) => onChange(spec.name, event.target.value)}
          onBlur={() => onBlur(spec.name)}
        />
      )}
      <p id={helpId} className="text-xs text-muted-foreground">
        {help}
      </p>
      {shownError && (
        <p id={errorId} className="flex items-center gap-1.5 text-xs text-danger">
          <CircleAlert aria-hidden="true" className="size-3.5 shrink-0" />
          <span>{shownError}</span>
        </p>
      )}
    </div>
  );
}
