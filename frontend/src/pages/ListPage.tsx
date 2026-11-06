import { CircleAlert, PackageSearch } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "../components/Button";
import { CenterState } from "../components/CenterState";
import { FeedFooter } from "../listings/FeedFooter";
import { ListingCard } from "../listings/ListingCard";
import { useFeed } from "../listings/useFeed";

// 2 columns on mobile, 3 at the sm breakpoint, 4 on desktop (E2.7 acceptance criteria).
const GRID = "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4";

// Start loading the next page about one screen before the user reaches the bottom.
const PRELOAD_MARGIN = "0px 0px 600px 0px";

export function ListPage() {
  const { items, status, focusIndex, loadMore, retry } = useFeed();
  const gridRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  // Auto-load (E4.3 design decision 4). Only watching while idle, so an error or the end of
  // the feed can't trigger requests. Re-created after every page: a fresh observer reports
  // the sentinel straight away, so a screen the first page doesn't fill keeps loading.
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (status !== "idle" || !sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        // Tabbing to "Load more" scrolls it into view, which auto-loads and removes the
        // button before Enter is pressed. Focus would drop to the page, so treat it as a press.
        loadMore({ focusNew: footerRef.current?.contains(document.activeElement) ?? false });
      },
      { rootMargin: PRELOAD_MARGIN },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [status, items.length, loadMore]);

  // After "Load more", focus the first new card, so keyboard users carry on from there
  // instead of landing back at the top of the page (decision 5).
  useEffect(() => {
    if (focusIndex === null) return;
    gridRef.current?.querySelector<HTMLElement>(`[data-feed-index="${focusIndex}"] a`)?.focus();
  }, [focusIndex]);

  if (status === "first-error") {
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

  if (status === "first-loading") {
    return (
      <div className={GRID} aria-busy>
        {/* Same boxes as ListingCard (photo, then a 20px title and a 24px price row), so
            nothing moves when the real cards replace them (E4.3 decision 7). */}
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="flex flex-col gap-2">
            <div className="aspect-[4/3] w-full animate-pulse rounded-md bg-border" />
            <div className="flex flex-col gap-1">
              <div className="h-5 w-4/5 animate-pulse rounded-sm bg-border" />
              <div className="h-6 w-1/3 animate-pulse rounded-sm bg-border" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <CenterState
        icon={<PackageSearch aria-hidden className="size-7" />}
        title="No listings yet"
        body="Be the first to sell something — tap Sell to get started."
      />
    );
  }

  return (
    <>
      <div ref={gridRef} className={GRID}>
        {items.map((listing, index) => (
          <div key={listing.id} data-feed-index={index}>
            <ListingCard listing={listing} />
          </div>
        ))}
      </div>
      <div ref={sentinelRef} aria-hidden />
      <div ref={footerRef}>
        <FeedFooter
          status={status}
          onLoadMore={() => loadMore({ focusNew: true })}
          onRetry={retry}
        />
      </div>
    </>
  );
}
