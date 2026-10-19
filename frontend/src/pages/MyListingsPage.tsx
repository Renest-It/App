import { CircleAlert, FilePen, Package, Tag } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { getMyListings } from "../api/client";
import type { ListingStatus, MyListing } from "../api/types";
import { Alert } from "../components/Alert";
import { Button, ButtonLink } from "../components/Button";
import { CenterState } from "../components/CenterState";
import { ListingCard } from "../listings/ListingCard";

type LoadState =
  { status: "loading" } | { status: "error" } | { status: "loaded"; listings: MyListing[] };

type Tab = "active" | "drafts" | "sold";

const TABS: { id: Tab; label: string; status: ListingStatus }[] = [
  { id: "active", label: "Active", status: "active" },
  { id: "drafts", label: "Drafts", status: "draft" },
  { id: "sold", label: "Sold", status: "sold" },
];

// Same grid as the home feed (ListPage): 2 columns on mobile, 3 at sm, 4 on desktop.
const GRID = "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4";

function parseTab(value: string | null): Tab {
  return TABS.some((t) => t.id === value) ? (value as Tab) : "active";
}

// The seller's own listings (E3.5), at /account/listings?tab=active|drafts|sold. The only
// place a seller can find their drafts, including ones a failed publish left behind (ADR 0010).
// The tab lives in the URL so it can be linked to and survives a refresh. One request loads
// all three tabs, so switching tabs is instant and every tab can show its count.
export function MyListingsPage() {
  const [searchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getMyListings()
      .then((listings) => {
        if (!cancelled) setState({ status: "loaded", listings });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  function retry() {
    setState({ status: "loading" });
    setAttempt((a) => a + 1);
  }

  const counts: Record<Tab, number> | null =
    state.status === "loaded"
      ? {
          active: state.listings.filter((l) => l.status === "active").length,
          drafts: state.listings.filter((l) => l.status === "draft").length,
          sold: state.listings.filter((l) => l.status === "sold").length,
        }
      : null;

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-display text-2xl font-bold text-text">My listings</h1>

      {state.status !== "error" && (
        <nav aria-label="Listing status" className="border-b border-border">
          <ul className="flex lg:gap-2">
            {TABS.map((t) => {
              const selected = t.id === tab;
              return (
                <li key={t.id} className="flex-1 lg:flex-none">
                  <Link
                    to={`?tab=${t.id}`}
                    replace
                    aria-current={selected ? "page" : undefined}
                    className={
                      "-mb-px flex min-h-11 items-center justify-center gap-1.5 border-b-2 px-3 " +
                      "text-body font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 " +
                      "focus-visible:outline-accent " +
                      (selected
                        ? "border-accent text-accent"
                        : "border-transparent text-text-muted hover:text-text")
                    }
                  >
                    {t.label}
                    {counts && (
                      <span
                        className={
                          "rounded-full px-2 py-0.5 text-xs font-semibold " +
                          (selected ? "bg-accent-soft text-accent" : "bg-border text-text-muted")
                        }
                      >
                        {counts[t.id]}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}

      {state.status === "loading" && (
        <div className={GRID} aria-busy>
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="aspect-[4/3] w-full animate-pulse rounded-md bg-border" />
              <div className="h-4 w-4/5 animate-pulse rounded-sm bg-border" />
              <div className="h-4 w-1/3 animate-pulse rounded-sm bg-border" />
            </div>
          ))}
        </div>
      )}

      {state.status === "error" && (
        <CenterState
          icon={<CircleAlert aria-hidden className="size-7" />}
          title="Couldn't load your listings"
          heading="h2"
          body="Check your connection and try again."
          danger
        >
          <div className="w-full max-w-xs">
            <Button onClick={retry}>Retry</Button>
          </div>
        </CenterState>
      )}

      {state.status === "loaded" && (
        <TabContent
          tab={tab}
          listings={state.listings.filter(
            (l) => l.status === TABS.find((t) => t.id === tab)!.status,
          )}
        />
      )}
    </div>
  );
}

function TabContent({ tab, listings }: { tab: Tab; listings: MyListing[] }) {
  if (listings.length === 0) {
    if (tab === "active") {
      return (
        <CenterState
          icon={<Package aria-hidden className="size-7" />}
          title="Nothing for sale yet"
          heading="h2"
          body="List your first item and it'll show up here."
        >
          <div className="w-full max-w-xs">
            <ButtonLink to="/sell">Sell an item</ButtonLink>
          </div>
        </CenterState>
      );
    }
    if (tab === "drafts") {
      return (
        <CenterState
          icon={<FilePen aria-hidden className="size-7" />}
          title="No drafts"
          heading="h2"
          body="A draft is a listing you started but haven't published yet. If posting ever stops partway, you'll find it here to finish."
        />
      );
    }
    return (
      <CenterState
        icon={<Tag aria-hidden className="size-7" />}
        title="Nothing sold yet"
        heading="h2"
        body="Listings you mark as sold will show up here."
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {tab === "drafts" && (
        <Alert variant="info">Drafts aren't visible to anyone else until you publish them.</Alert>
      )}
      <div className={GRID}>
        {listings.map((listing) => (
          <ListingCard key={listing.id} listing={listing} status={listing.status} />
        ))}
      </div>
    </div>
  );
}
