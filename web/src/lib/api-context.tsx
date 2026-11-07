import { createContext, useContext, type ReactNode } from "react";

import type { Api } from "@/lib/api";

const ApiContext = createContext<Api | null>(null);

/** Hands the run service client to every page and component below it (ADR-008). */
export function ApiProvider({ api, children }: { api: Api; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

/** The run service client; the only way a component reads or changes data. */
export function useApi(): Api {
  const api = useContext(ApiContext);
  if (api === null) throw new Error("useApi() needs an <ApiProvider> above it");
  return api;
}
