import { useEffect, useState } from "react";
import { getCategories } from "../api/client";
import type { Category } from "../api/types";

export type CategoriesState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; categories: Category[] };

// The category options for the listing form (create and edit).
export function useCategories() {
  const [state, setState] = useState<CategoriesState>({ status: "loading" });

  useEffect(() => {
    getCategories()
      .then((categories) => setState({ status: "loaded", categories }))
      .catch((e) =>
        setState({
          status: "error",
          message: e instanceof Error ? e.message : "Could not load categories",
        }),
      );
  }, []);

  return state;
}
