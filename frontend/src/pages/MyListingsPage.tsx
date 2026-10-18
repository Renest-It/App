import { CircleAlert, CircleCheck, FilePen, Tag } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { getMyListings } from "../api/client";
import type { ListingStatus, MyListing } from "../api/types";
import { Alert } from "../components/Alert";
import { Button, ButtonLink } from "../components/Button";
import { CenterState } from "../components/CenterState";
import { ListingCard } from "../listings/ListingCard";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; listings: MyListing[] };

// The ?tab= value for each tab. Active is the default, so it's the one tab with no param.
const TABS: { tab: string; status: ListingStatus; label: string }[] = [
  { tab: "active", status: "active", label: "Active" },
  { tab: "drafts", status: "draft", label: "Drafts" },
  { tab: "sold", status: "sold", label: "Sold" },
];

// Same grid as the home feed (ListPage), so the cards are the same size in both places.
const GRID = "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4";

// My Listings (E3.5): the seller's own listings split into Active, Drafts, and Sold. Reached
// from the Account page. It's the only way back to a draft, including one left behind by a
// publish that failed partway (E2). Each card opens the detail page, where E3.4's actions are.
export function MyListingsPage() {
  const [searchParams] = useSearchParams();
  // An unknown ?tab= falls back to Active rather than showing an empty page.
  const current = TABS.find((t) => t.tab === searchParams.get("tab")) ?? TABS[0];

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  // One request for all three tabs (not one per tab), so every tab's count is known up front
  // and switching tabs is instant. The API already sorts newest first.
  useEffect(() => {
    let cancelled = false;

    getMyListings()
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

  const listings = state.status === "loaded" ? state.listings : [];
  const shown = listings.filter((l) => l.status === current.status);

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-display text-2xl font-bold text-text">My Listings</h1>

      {state.status !== "error" && (
        <nav aria-label="Listing status" className="border-b border-border">
          <ul className="flex gap-6">
            {TABS.map((t) => {
              const active = t.tab === current.tab;
              const count = listings.filter((l) => l.status === t.status).length;
              return (
                <li key={t.tab}>
                  <Link
                    // replace: switching tabs shouldn't fill the back button with tab changes.
                    to={{ search: t.tab === "active" ? "" : `?tab=${t.tab}` }}
                    replace
                    aria-current={active ? "page" : undefined}
                    className={
                      "-mb-px flex min-h-11 items-center gap-2 border-b-2 text-body font-semibold " +
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
                      (active
                        ? "border-accent text-accent"
                        : "border-transparent text-text-muted hover:text-text")
                    }
                  >
                    {t.label}
                    {state.status === "loaded" && (
                      <span
                        className={
                          "rounded-full px-2 py-0.5 text-xs " +
                          (active ? "bg-accent-soft" : "bg-border")
                        }
                      >
                        {count}
                        <span className="sr-only"> listings</span>
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}

      {state.status === "error" ? (
        <CenterState
          icon={<CircleAlert aria-hidden className="size-7" />}
          title="Couldn't load your listings"
          body="Check your connection and try again."
          danger
        >
          <Button className="w-auto min-w-40" onClick={retry}>
            Retry
          </Button>
        </CenterState>
      ) : state.status === "loading" ? (
        <div className={GRID} aria-busy>
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="aspect-[4/3] w-full animate-pulse rounded-md bg-border" />
              <div className="h-4 w-4/5 animate-pulse rounded-sm bg-border" />
              <div className="h-4 w-1/3 animate-pulse rounded-sm bg-border" />
            </div>
          ))}
        </div>
      ) : shown.length === 0 ? (
        <EmptyState status={current.status} />
      ) : (
        <>
          {current.status === "draft" && (
            <Alert variant="info">
              Drafts are only visible to you. Open one to finish it and publish it.
            </Alert>
          )}
          <div className={GRID}>
            {shown.map((listing) => (
              <ListingCard key={listing.id} listing={listing} status={listing.status} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function EmptyState({ status }: { status: ListingStatus }) {
  if (status === "active") {
    return (
      <CenterState
        icon={<Tag aria-hidden className="size-7" />}
        title="No active listings"
        body="Got something you don't need anymore? List it and other Creighton students can find it."
      >
        <ButtonLink to="/sell" className="w-auto min-w-40">
          Create a listing
        </ButtonLink>
      </CenterState>
    );
  }
  if (status === "draft") {
    // Most people only find out they have drafts by landing here, so this explains what one is.
    return (
      <CenterState
        icon={<FilePen aria-hidden className="size-7" />}
        title="No drafts"
        body="A draft is a listing that hasn't been published yet, and only you can see it. If a listing doesn't finish publishing, it's saved here so you can pick up where you left off."
      />
    );
  }
  return (
    <CenterState
      icon={<CircleCheck aria-hidden className="size-7" />}
      title="Nothing sold yet"
      body="Listings you mark as sold show up here."
    />
  );
}
