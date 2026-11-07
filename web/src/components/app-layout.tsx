import { Outlet } from "react-router";

/** Stub from the shared setup; part W1 replaces it with the skip link, top bar and main. */
export function AppLayout() {
  return (
    <main id="main">
      <Outlet />
    </main>
  );
}
