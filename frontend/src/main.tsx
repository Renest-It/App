import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource-variable/instrument-sans";
import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";
import { setAuthFailureHandler } from "./api/client";
import { handleAuthFailure } from "./auth/authFailure";
import { AuthProvider } from "./auth/AuthProvider";
import { router } from "./router";

// When the API rejects the session (expired, blocked account), sign out and go to log in.
setAuthFailureHandler((reason) => handleAuthFailure(reason, router));

// VITE_USE_MOCKS=true serves E2's API from MSW (src/mocks/) instead of the real backend.
// The dynamic import keeps MSW out of builds that don't use it.
async function startMocks() {
  if (import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledFrame: "bypass" });
}

startMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </StrictMode>,
  );
});
