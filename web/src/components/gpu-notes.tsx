/**
 * "How training uses your NVIDIA GPU" (AC4.6.9): a disclosure at the end of the dials panel that
 * lists what every fine-tune already does on the GPU (`GPU_NOTES`), each with one line on why.
 * Static text; opening it never touches a dial value or the Start button.
 */
import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { GPU_NOTES } from "@/lib/dial-info";

/** The look of every small disclosure button of the dials panel: text, chevron, visible focus. */
export const DISCLOSURE_BUTTON_CLASS =
  "group inline-flex min-h-8 items-center gap-1.5 rounded-sm px-1.5 text-left text-xs " +
  "text-muted-foreground underline-offset-4 outline-none transition-[color,box-shadow] " +
  "hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring " +
  "[&_svg]:size-3.5 [&_svg]:shrink-0";

export function GpuNotes() {
  const listId = useId();
  const [open, setOpen] = useState(false);

  return (
    <div className="grid justify-items-start gap-2">
      <button
        type="button"
        className={DISCLOSURE_BUTTON_CLASS}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((current) => !current)}
      >
        How training uses your NVIDIA GPU
        <ChevronDown
          aria-hidden="true"
          className="transition-transform group-aria-expanded:rotate-180"
        />
      </button>
      {open && (
        <ul
          id={listId}
          className="grid w-full list-none gap-3 rounded-sm border border-hairline bg-panel p-3 text-xs text-muted-foreground"
        >
          {GPU_NOTES.map((note) => (
            <li key={note.name}>
              <span className="block font-medium text-foreground">{note.name}</span>{" "}
              <span>{note.why}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
