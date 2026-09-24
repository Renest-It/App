import { createBrowserRouter } from "react-router";
import { GuestOnly } from "./auth/GuestOnly";
import { Layout } from "./components/Layout";
import { CheckEmailPage } from "./pages/CheckEmailPage";
import { ConfirmPage } from "./pages/ConfirmPage";
import { ListPage } from "./pages/ListPage";
import { LoginPage } from "./pages/LoginPage";
import { NewListingPage } from "./pages/NewListingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SignUpPage } from "./pages/SignUpPage";

export const router = createBrowserRouter([
  // Auth pages sit outside Layout so they don't get the app's nav bar.
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
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <ListPage /> },
      { path: "new", element: <NewListingPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
