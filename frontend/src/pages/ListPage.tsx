import { CircleAlert, PackageSearch, SearchX } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../components/Button";
import { CenterState } from "../components/CenterState";
import { FeedFooter } from "../listings/FeedFooter";
import { FilterBar } from "../listings/FilterBar";
import { ListingCard } from "../listings/ListingCard";
import { useCategories } from "../listings/useCategories";
import { useFeed } from "../listings/useFeed";

// 2 columns on mobile, 3 at the sm breakpoint, 4 on desktop (E2.7 acceptance criteria).
// [&_a]:scroll-mt: a card focused by Shift+Tab scrolls clear of the pinned filter bar (64px
// plus the safe area), with 8px to spare.
const GRID =
  "grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-4 " +
  "[&_a]:scroll-mt-[calc(4.5rem+env(safe-area-inset-top))]";

// Start loading the next page about one screen before the user reaches the bottom.
const PRELOAD_MARGIN = "0px 0px 600px 0px";

export function ListPage() {
  // The URL is the only copy of the filter (E5.2 design decision 2): /?category=<slug>.
  const [searchParams, setSearchParams] = useSearchParams();
  const category = searchParams.get("category");
  const { items, status, focusIndex, errorCode, loadMore, retry } = useFeed(
    category === null ? {} : { category },
  );
  const categories = useCategories();
  const gridRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  // A new history entry per filter, so Back and Forward move between them. A new location
  // also starts at the top (ScrollRestoration, decision 3). The current chip does nothing,
  // rather than adding a duplicate entry.
  function selectCategory(slug: string | null) {
    if (slug === category) return;
    setSearchParams(slug === null ? {} : { category: slug });
  }

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

  // The filter bar stays above every state, so the user can always switch category.
  const page = (content: ReactNode) => (
    <>
      <FilterBar selected={category} onSelect={selectCategory} />
      {content}
    </>
  );

  const clearFilter = (
    <Button className="w-auto! min-w-40" onClick={() => selectCategory(null)}>
      Clear filter
    </Button>
  );

  // A hand-edited slug (decision 5). Retrying would only fail again.
  if (status === "first-error" && errorCode === "unknown_category") {
    return page(
      <CenterState
        icon={<SearchX aria-hidden className="size-7" />}
        title="Category not found"
        body="That category doesn't exist. It may have been mistyped."
      >
        {clearFilter}
      </CenterState>,
    );
  }

  if (status === "first-error") {
    return page(
      <CenterState
        icon={<CircleAlert aria-hidden className="size-7" />}
        title="Couldn't load listings"
        body="Check your connection and try again."
        danger
      >
        <Button className="w-auto! min-w-40" onClick={retry}>
          Retry
        </Button>
      </CenterState>,
    );
  }

  if (status === "first-loading") {
    return page(
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
      </div>,
    );
  }

  if (items.length === 0 && category !== null) {
    const name =
      categories.status === "loaded"
        ? categories.categories.find((c) => c.slug === category)?.name
        : undefined;
    return page(
      <CenterState
        icon={<PackageSearch aria-hidden className="size-7" />}
        title={name ? `Nothing in ${name} yet` : "Nothing in this category yet"}
        body="Check back soon, or browse everything."
      >
        {clearFilter}
      </CenterState>,
    );
  }

  if (items.length === 0) {
    return page(
      <CenterState
        icon={<PackageSearch aria-hidden className="size-7" />}
        title="No listings yet"
        body="Be the first to sell something — tap Sell to get started."
      />,
    );
  }

  return page(
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
    </>,
  );
}
