import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { ListPage } from "./pages/ListPage";
import { NewListingPage } from "./pages/NewListingPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export const router = createBrowserRouter([
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
