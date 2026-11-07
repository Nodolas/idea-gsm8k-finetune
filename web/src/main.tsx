import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import "@/index.css";
import { createApi } from "@/lib/api";
import { ApiProvider } from "@/lib/api-context";
import { createAppRouter } from "@/router";

const container = document.getElementById("root");
if (container === null) throw new Error("index.html has no #root element");

createRoot(container).render(
  <StrictMode>
    <ApiProvider api={createApi()}>
      <RouterProvider router={createAppRouter("browser")} />
    </ApiProvider>
  </StrictMode>,
);
