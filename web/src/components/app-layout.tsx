import { useRef, type MouseEvent } from "react";
import { Outlet } from "react-router";

import { TopBar } from "@/components/top-bar";
import { useStatus } from "@/lib/queries";

/**
 * The shell every page shares (US4.1): the skip link as the first Tab stop, the top bar (which
 * polls the service status every 5 s for the running tag) and `<main id="main">`.
 */
export function AppLayout() {
  const status = useStatus(5000);
  const mainRef = useRef<HTMLElement>(null);
  const activeRunId =
    status.state === "ready" && status.data.status === "RUNNING" ? status.data.run_id : null;

  const skipToMain = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    mainRef.current?.focus();
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main"
        onClick={skipToMain}
        className="sr-only rounded-sm bg-panel px-4 py-2 text-sm text-ink focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
      >
        Skip to content
      </a>
      <TopBar activeRunId={activeRunId} />
      <main id="main" ref={mainRef} tabIndex={-1} className="outline-none">
        <Outlet />
      </main>
    </div>
  );
}
