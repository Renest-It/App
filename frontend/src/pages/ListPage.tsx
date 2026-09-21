import { useEffect, useState } from "react";
import { getListings } from "../api/client";
import { formatPriceCents } from "../api/format";
import type { Listing } from "../api/types";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; listings: Listing[] };

export function ListPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    getListings()
      .then((listings) => {
        if (!cancelled) setState({ status: "loaded", listings });
      })
      .catch((e) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: e instanceof Error ? e.message : "Something went wrong",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [attempt]);

  function retry() {
    setState({ status: "loading" });
    setAttempt((a) => a + 1);
  }

  if (state.status === "error") {
    return (
      <div>
        <h1>Listings</h1>
        <p>Could not load listings: {state.message}</p>
        <button type="button" onClick={retry}>
          Retry
        </button>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div>
        <h1>Listings</h1>
        <p>Loading…</p>
      </div>
    );
  }

  if (state.listings.length === 0) {
    return (
      <div>
        <h1>Listings</h1>
        <p>No listings yet</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Listings</h1>
      <ul>
        {state.listings.map((listing) => (
          <li key={listing.id}>
            {listing.title} — {formatPriceCents(listing.price_cents)} — {listing.category.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
