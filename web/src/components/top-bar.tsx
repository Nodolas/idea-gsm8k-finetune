import { Link, NavLink } from "react-router";

import { cn } from "@/lib/utils";

export interface TopBarProps {
  /** The run that is active now; shows the running tag linking to Training when set. */
  activeRunId?: string | null;
}

const pageLink = ({ isActive }: { isActive: boolean }) =>
  cn(
    "rounded-sm px-1 py-1 text-sm text-ink-muted transition-colors duration-150 hover:text-ink",
    isActive && "text-ink underline decoration-orange decoration-1 underline-offset-[6px]",
  );

/**
 * The bar on every page (US4.1): the wordmark linking home, the running tag while a run is
 * active, then Scores, Training and Reasoning (US10.4); the current page's link is underlined
 * and carries `aria-current="page"` (set by NavLink), so colour is never the only marker.
 */
export function TopBar({ activeRunId = null }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 border-b-[0.5px] border-hairline bg-background">
      <nav aria-label="Main" className="flex h-14 items-center gap-6 px-[var(--gutter)]">
        <Link
          to="/"
          aria-label="gsm8k home"
          className="mr-auto rounded-sm font-sans text-lg font-semibold tracking-tight text-ink lowercase"
        >
          gsm8k
        </Link>
        {activeRunId ? (
          <Link
            to="/training"
            className="num inline-flex items-center gap-2 rounded-sm border-[0.5px] border-hairline px-2 py-0.5 text-xs text-ink"
          >
            <span aria-hidden="true" className="text-orange">
              ●
            </span>
            <span>RUNNING {activeRunId}</span>
          </Link>
        ) : null}
        <NavLink to="/scores" end className={pageLink}>
          Scores
        </NavLink>
        <NavLink to="/training" end className={pageLink}>
          Training
        </NavLink>
        <NavLink to="/reasoning" end className={pageLink}>
          Reasoning
        </NavLink>
      </nav>
    </header>
  );
}
