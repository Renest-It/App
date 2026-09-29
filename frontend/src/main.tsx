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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </StrictMode>,
);
