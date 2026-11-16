import { inlinePieces, textBlocks } from "@/lib/course";
import { cn } from "@/lib/utils";

function Inline({ line }: { line: string }) {
  return (
    <>
      {inlinePieces(line).map((piece, i) => {
        if (piece.kind === "strong") return <strong key={i}>{piece.text}</strong>;
        if (piece.kind === "code") {
          return (
            <code key={i} className="num rounded-sm bg-panel px-1 text-[0.9em]">
              {piece.text}
            </code>
          );
        }
        return <span key={i}>{piece.text}</span>;
      })}
    </>
  );
}

/**
 * Markdown paragraphs from the service as plain elements (no HTML is ever injected): blank lines
 * split paragraphs, `- ` lines make a list, `**bold**` and `code` are marked. Each block keeps at
 * most 75 characters per line (AC12.5.13).
 */
export function Prose({ text, className }: { text: string; className?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {textBlocks(text).map((block, i) =>
        block.kind === "p" ? (
          <p key={i} className={cn("max-w-[75ch] text-ink", className)}>
            <Inline line={block.text} />
          </p>
        ) : (
          <ul key={i} className={cn("max-w-[75ch] list-disc pl-5 text-ink", className)}>
            {block.items.map((item, j) => (
              <li key={j}>
                <Inline line={item} />
              </li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}
