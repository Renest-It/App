import { useCallback, useEffect, useReducer, useRef } from "react";
import { useNavigationType } from "react-router";
import { ApiError, getListingsPage } from "../api/client";
import type { Listing, ListingsPage } from "../api/types";
import { useAuth } from "../auth/useAuth";

export type FeedStatus =
  | "first-loading" // no page yet
  | "first-error" // the first page failed
  | "idle" // more pages exist, nothing in flight
  | "loading-more"
  | "more-error" // a later page failed; what's loaded stays
  | "done"; // next_cursor was null

type FeedState = {
  items: Listing[];
  cursor: string | null;
  status: FeedStatus;
  // Index of the first card a "Load more" press added, for ListPage to move focus to.
  focusIndex: number | null;
};

type FeedAction =
  | { type: "reset" }
  | { type: "request" }
  | { type: "page"; page: ListingsPage; focusNew: boolean }
  | { type: "failed" };

const INITIAL: FeedState = { items: [], cursor: null, status: "first-loading", focusIndex: null };

function reducer(state: FeedState, action: FeedAction): FeedState {
  switch (action.type) {
    case "reset":
      return INITIAL;
    case "request":
      return {
        ...state,
        status: state.items.length === 0 ? "first-loading" : "loading-more",
      };
    case "page": {
      // Keyset pages never overlap, but a duplicate key would be a confusing bug: drop it.
      const seen = new Set(state.items.map((item) => item.id));
      const added = action.page.items.filter((item) => !seen.has(item.id));
      return {
        items: [...state.items, ...added],
        cursor: action.page.next_cursor,
        status: action.page.next_cursor === null ? "done" : "idle",
        focusIndex: action.focusNew && added.length > 0 ? state.items.length : null,
      };
    }
    case "failed":
      // An error never clears what's loaded.
      return { ...state, status: state.items.length === 0 ? "first-error" : "more-error" };
  }
}

// The feed as it was when the user left the home page, so Back can show it again (scroll
// restoration, E4.3). In memory only: a reload starts fresh. Keyed by user and filter, so it's
// never shown to someone else or under another filter.
let snapshot: { key: string; state: FeedState } | null = null;

function restored(key: string): FeedState | null {
  if (snapshot?.key !== key) return null;
  const { state } = snapshot;
  // Nothing to keep a place in. Load fresh: "No listings yet" may be out of date (e.g. Back
  // after publishing the first listing).
  if (state.items.length === 0) return null;
  // Left mid-request or after an error: carry on from the same cursor.
  const status = state.status === "done" ? "done" : "idle";
  return { ...state, status, focusIndex: null };
}

export type Feed = {
  items: Listing[];
  status: FeedStatus;
  focusIndex: number | null;
  loadMore: (options?: { focusNew?: boolean }) => void;
  retry: () => void;
};

// The home feed, one page at a time (E4.3, ADR 0011). Every way of loading more goes through
// loadMore(), which starts at most one request at a time. E5 passes a filter: changing it
// starts again from the first page.
export function useFeed(filter: Record<string, string | number> = {}): Feed {
  const { user } = useAuth();
  const key = `${user?.id ?? ""}|${JSON.stringify(filter)}`;
  const navigationType = useNavigationType();

  const [state, dispatch] = useReducer(
    reducer,
    null,
    () => (navigationType === "POP" && restored(key)) || INITIAL,
  );

  // Refs, not state: two calls in the same tick (an observer firing twice, a click during an
  // auto-load) must both see the request the first one started.
  const inFlight = useRef(false);
  // Bumped on every reset and unmount; a response from an older generation is dropped.
  const generation = useRef(0);
  // The key the current items belong to. Starts set when the feed was restored, so the
  // effect below doesn't fetch it again.
  const loadedKey = useRef(state === INITIAL ? null : key);

  const fetchPage = useCallback((startCursor: string | null, startFocusNew = false) => {
    function run(cursor: string | null, focusNew: boolean) {
      if (inFlight.current) return;
      inFlight.current = true;
      const requestGeneration = generation.current;
      dispatch({ type: "request" });

      getListingsPage(cursor ? { cursor } : {})
        .then((page) => {
          if (requestGeneration !== generation.current) return;
          inFlight.current = false;
          dispatch({ type: "page", page, focusNew });
        })
        .catch((e) => {
          if (requestGeneration !== generation.current) return;
          inFlight.current = false;
          if (cursor && e instanceof ApiError && e.code === "invalid_cursor") {
            // The server can't use this cursor any more: start again from the first page.
            generation.current += 1;
            dispatch({ type: "reset" });
            run(null, false);
            return;
          }
          dispatch({ type: "failed" });
        });
    }
    run(startCursor, startFocusNew);
  }, []);

  // First page on mount, and again whenever the user or filter changes.
  useEffect(() => {
    if (loadedKey.current !== key) {
      loadedKey.current = key;
      generation.current += 1;
      inFlight.current = false;
      dispatch({ type: "reset" });
      fetchPage(null);
    }
    return () => {
      // A first page still loading belongs to no one now. StrictMode's dev-only remount (or a
      // real one) should fetch it again rather than wait for a response that will be dropped.
      if (inFlight.current) loadedKey.current = null;
      generation.current += 1;
      inFlight.current = false;
    };
  }, [key, fetchPage]);

  useEffect(() => {
    snapshot = { key, state };
  }, [key, state]);

  const { status, cursor } = state;

  const loadMore = useCallback(
    ({ focusNew = false }: { focusNew?: boolean } = {}) => {
      if (status === "idle") fetchPage(cursor, focusNew);
    },
    [status, cursor, fetchPage],
  );

  const retry = useCallback(() => {
    if (status === "first-error") fetchPage(null);
    else if (status === "more-error") fetchPage(cursor);
  }, [status, cursor, fetchPage]);

  return { items: state.items, status, focusIndex: state.focusIndex, loadMore, retry };
}
