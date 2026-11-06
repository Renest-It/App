import { useCallback, useEffect, useLayoutEffect, useReducer, useRef } from "react";
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
  // The user and filter these items belong to (see useFeed's key). Right after the filter
  // changes, one render still holds the old filter's state; this keeps it from being saved
  // under the new filter.
  key: string | null;
  items: Listing[];
  cursor: string | null;
  status: FeedStatus;
  // Index of the first card a "Load more" press added, for ListPage to move focus to.
  focusIndex: number | null;
  // The API error code when the first page failed, e.g. "unknown_category" (E5.2).
  errorCode: string | null;
};

type FeedAction =
  // key: the feed to start; omitted to start the current one again.
  | { type: "reset"; key?: string }
  | { type: "restore"; state: FeedState }
  | { type: "request" }
  | { type: "page"; page: ListingsPage; focusNew: boolean }
  | { type: "failed"; code: string | null };

const INITIAL: FeedState = {
  key: null,
  items: [],
  cursor: null,
  status: "first-loading",
  focusIndex: null,
  errorCode: null,
};

function reducer(state: FeedState, action: FeedAction): FeedState {
  switch (action.type) {
    case "reset":
      return { ...INITIAL, key: action.key ?? state.key };
    case "restore":
      return action.state;
    case "request":
      return {
        ...state,
        status: state.items.length === 0 ? "first-loading" : "loading-more",
        errorCode: null,
      };
    case "page": {
      // Keyset pages never overlap, but a duplicate key would be a confusing bug: drop it.
      const seen = new Set(state.items.map((item) => item.id));
      const added = action.page.items.filter((item) => !seen.has(item.id));
      return {
        key: state.key,
        items: [...state.items, ...added],
        cursor: action.page.next_cursor,
        status: action.page.next_cursor === null ? "done" : "idle",
        focusIndex: action.focusNew && added.length > 0 ? state.items.length : null,
        errorCode: null,
      };
    }
    case "failed":
      // An error never clears what's loaded.
      return state.items.length === 0
        ? { ...state, status: "first-error", errorCode: action.code }
        : { ...state, status: "more-error" };
  }
}

// The feeds as they were when the user left them, so Back can show them again (scroll
// restoration, E4.3). In memory only: a reload starts fresh. Keyed by user and filter, so a
// feed is never shown to someone else or under another filter. Several are kept, so Back
// between filters restores each one too (E5.2 design decision 4).
const SNAPSHOT_LIMIT = 5;
const snapshots = new Map<string, FeedState>();

function remember(key: string, state: FeedState) {
  // Re-inserting moves the key to the end, so the first key is always the oldest.
  snapshots.delete(key);
  snapshots.set(key, state);
  if (snapshots.size > SNAPSHOT_LIMIT) snapshots.delete(snapshots.keys().next().value!);
}

function restored(key: string): FeedState | null {
  const state = snapshots.get(key);
  if (state === undefined) return null;
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
  errorCode: string | null;
  loadMore: (options?: { focusNew?: boolean }) => void;
  retry: () => void;
};

export type FeedFilter = { category?: string };

// The home feed, one page at a time (E4.3, ADR 0011). Every way of loading more goes through
// loadMore(), which starts at most one request at a time. The filter is sent with every page;
// changing it starts again from the first page (E5.2).
export function useFeed(filter: FeedFilter = {}): Feed {
  const { user } = useAuth();
  const key = `${user?.id ?? ""}|${JSON.stringify(filter)}`;
  const navigationType = useNavigationType();

  // The latest filter and navigation type, read by fetchPage (so it stays one stable
  // function) and by the reset effect (so only a key change re-runs it). A layout effect
  // runs before every regular effect, so they're current by the time those read them.
  const filterRef = useRef(filter);
  const navigationTypeRef = useRef(navigationType);
  useLayoutEffect(() => {
    filterRef.current = filter;
    navigationTypeRef.current = navigationType;
  });

  const [state, dispatch] = useReducer(
    reducer,
    null,
    () => (navigationType === "POP" && restored(key)) || { ...INITIAL, key },
  );

  // Refs, not state: two calls in the same tick (an observer firing twice, a click during an
  // auto-load) must both see the request the first one started.
  const inFlight = useRef(false);
  // Bumped on every reset and unmount; a response from an older generation is dropped.
  const generation = useRef(0);
  // The key the current items belong to. Starts set when the feed was restored, so the
  // effect below doesn't fetch it again.
  const loadedKey = useRef(state.items.length > 0 ? key : null);

  const fetchPage = useCallback((startCursor: string | null, startFocusNew = false) => {
    function run(cursor: string | null, focusNew: boolean) {
      if (inFlight.current) return;
      inFlight.current = true;
      const requestGeneration = generation.current;
      dispatch({ type: "request" });

      getListingsPage({ ...filterRef.current, ...(cursor ? { cursor } : {}) })
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
          dispatch({ type: "failed", code: (e instanceof ApiError && e.code) || null });
        });
    }
    run(startCursor, startFocusNew);
  }, []);

  // First page on mount, and again whenever the user or filter changes. Back to a filter
  // left earlier (e.g. Furniture → Kitchen → Back) shows it as it was instead (E5.2).
  useEffect(() => {
    if (loadedKey.current !== key) {
      loadedKey.current = key;
      generation.current += 1;
      inFlight.current = false;
      const saved = navigationTypeRef.current === "POP" ? restored(key) : null;
      if (saved) {
        dispatch({ type: "restore", state: saved });
      } else {
        dispatch({ type: "reset", key });
        fetchPage(null);
      }
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
    if (state.key === key) remember(key, state);
  }, [key, state]);

  // What to show. Until the effect above catches up with a new key, show what it's about to
  // switch to, never the old filter's listings. Back then restores the scroll position
  // against the right page (ScrollRestoration runs before effects).
  const view =
    state.key === key ? state : (navigationType === "POP" && restored(key)) || { ...INITIAL, key };
  const { status, cursor } = view;

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

  return {
    items: view.items,
    status,
    focusIndex: view.focusIndex,
    errorCode: view.errorCode,
    loadMore,
    retry,
  };
}
