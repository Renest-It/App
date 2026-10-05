import { PackageSearch, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { getListings } from "../api/client";
import { Button } from "../components/Button";
import { ListingCard } from "../listings/ListingCard";
import type { Listing } from "../api/types";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; listings: Listing[] };

// 2 columns on mobile, 3 at the sm breakpoint, 4 on desktop (E2.7 acceptance criteria).
const GRID = "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4";

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
      <CenterState
        icon={<CircleAlert aria-hidden className="size-7" />}
        title="Couldn't load listings"
        body="Check your connection and try again."
        danger
      >
        <Button className="w-auto min-w-40" onClick={retry}>
          Retry
        </Button>
      </CenterState>
    );
  }

  if (state.status === "loading") {
    return (
      <div className={GRID} aria-busy>
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="flex flex-col gap-2">
            <div className="aspect-[4/3] w-full animate-pulse rounded-md bg-border" />
            <div className="h-4 w-4/5 animate-pulse rounded-sm bg-border" />
            <div className="h-4 w-1/3 animate-pulse rounded-sm bg-border" />
          </div>
        ))}
      </div>
    );
  }

  if (state.listings.length === 0) {
    return (
      <CenterState
        icon={<PackageSearch aria-hidden className="size-7" />}
        title="No listings yet"
        body="Be the first to sell something — tap Sell to get started."
      />
    );
  }

  return (
    <div className={GRID}>
      {state.listings.map((listing) => (
        <ListingCard key={listing.id} listing={listing} />
      ))}
    </div>
  );
}

function CenterState({
  icon,
  title,
  body,
  danger = false,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  danger?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
      <div
        className={
          "flex size-14 items-center justify-center rounded-full " +
          (danger ? "bg-danger-soft-strong text-danger" : "bg-accent-soft text-accent")
        }
      >
        {icon}
      </div>
      <h1 className="font-display text-lg font-bold text-text">{title}</h1>
      <p className="text-body max-w-xs text-text-muted">{body}</p>
      {children}
    </div>
  );
}
