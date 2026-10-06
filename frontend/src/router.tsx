import { createBrowserRouter, Navigate } from "react-router";
import { GuestOnly } from "./auth/GuestOnly";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./components/AppShell";
import { AccountPage } from "./pages/AccountPage";
import { CheckEmailPage } from "./pages/CheckEmailPage";
import { ConfirmPage } from "./pages/ConfirmPage";
import { CreateListingPage } from "./pages/CreateListingPage";
import { ComponentGallery } from "./pages/dev/ComponentGallery";
import { ListingDetailPage } from "./pages/ListingDetailPage";
import { ListPage } from "./pages/ListPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SignUpPage } from "./pages/SignUpPage";

export const router = createBrowserRouter([
  // Auth pages sit outside the app shell so they don't get the navigation.
  {
    path: "/signup",
    element: (
      <GuestOnly>
        <SignUpPage />
      </GuestOnly>
    ),
  },
  {
    path: "/login",
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    ),
  },
  { path: "/check-email", element: <CheckEmailPage /> },
  // Where verification-email links land (see confirmRedirectUrl in auth/AuthProvider.tsx).
  { path: "/auth/confirm", element: <ConfirmPage /> },
  // Every in-app page is a child of this route, and RequireAuth makes all of them login-only
  // (including pages added later). Logged-out visitors go to /login?next=<path>.
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <ListPage /> },
      { path: "listings/:id", element: <ListingDetailPage /> },
      { path: "sell", element: <CreateListingPage /> },
      // Old create-listing URL, kept working for bookmarks.
      { path: "new", element: <Navigate to="/sell" replace /> },
      { path: "account", element: <AccountPage /> },
      // Dev-only preview route for E2.4 review (SCRUM-35). Not linked from the app's nav.
      { path: "dev/components", element: <ComponentGallery /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
