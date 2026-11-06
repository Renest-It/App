import { useEffect, useState } from "react";
import { getCategories } from "../api/client";
import type { Category } from "../api/types";

export type CategoriesState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; categories: Category[] };

// Loaded once per page load and reused, so the home page's filter bar doesn't flicker each time
// you come back to it (E5.2). Components mounting together share one request. A failure isn't
// kept: the next mount tries again.
let cached: Category[] | null = null;
let pending: Promise<Category[]> | null = null;

function loadCategories() {
  pending ??= getCategories().then(
    (categories) => {
      cached = categories;
      return categories;
    },
    (e) => {
      pending = null;
      throw e;
    },
  );
  return pending;
}

// The categories, for the listing form (create and edit) and the home page's filter bar.
export function useCategories() {
  const [state, setState] = useState<CategoriesState>(() =>
    cached ? { status: "loaded", categories: cached } : { status: "loading" },
  );

  useEffect(() => {
    if (cached) return;
    loadCategories()
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
