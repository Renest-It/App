import { CircleAlert, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { ApiError, getListing } from "../api/client";
import { formatPriceCents } from "../api/format";
import type { ListingDetail } from "../api/types";
import { Alert } from "../components/Alert";
import { Button, ButtonLink } from "../components/Button";
import { CategoryChip } from "../components/CategoryChip";
import { CenterState } from "../components/CenterState";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../auth/useAuth";
import { PhotoGallery } from "../listings/PhotoGallery";
import { SellerActions } from "../listings/SellerActions";
import { formatRelativeTime } from "../listings/time";

type LoadState =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "loaded"; listing: ListingDetail };

// The listing detail page (E2.6). Loading placeholder, 404, retryable error, and the loaded
// listing itself — photo gallery, price-or-Free, description, and the seller section. The
// owner gets E3.4's seller actions; the contact button (E6) only reserves its layout space.
export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  // Keyed by id: navigating to a different listing fully remounts this, which is what resets
  // state to "loading" for the new id — simpler than resetting it by hand inside an effect.
  return <ListingDetailBody key={id} id={id} />;
}

function ListingDetailBody({ id }: { id?: string }) {
  const { currentUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  // One-time banner for a seller arriving right after publishing ("Your listing is live!") or
  // saving an edit ("Changes saved."). Read once from navigation state, then immediately
  // replaced out of history so a refresh (a fresh navigation entry with no state) doesn't
  // show it again.
  const [arrivedFrom] = useState(() => {
    const state = location.state as { justPublished?: boolean; justSaved?: boolean } | null;
    return { published: state?.justPublished === true, saved: state?.justSaved === true };
  });
  useEffect(() => {
    if (arrivedFrom.published || arrivedFrom.saved) {
      navigate(location.pathname, { replace: true });
    }
    // Only ever run once, right after mount — rerunning on navigate/location changes would
    // immediately clear the state we just read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    getListing(id)
      .then((listing) => {
        if (!cancelled) setState({ status: "loaded", listing });
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.code === "listing_not_found") {
          setState({ status: "not-found" });
        } else {
          setState({
            status: "error",
            message: e instanceof Error ? e.message : "Something went wrong",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  function retry() {
    setState({ status: "loading" });
    setAttempt((a) => a + 1);
  }

  if (state.status === "loading") {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4" aria-busy>
        <div className="aspect-[4/3] w-full animate-pulse rounded-md bg-border" />
        <div className="h-7 w-2/3 animate-pulse rounded-sm bg-border" />
        <div className="h-5 w-1/4 animate-pulse rounded-sm bg-border" />
        <div className="flex flex-col gap-2">
          <div className="h-4 w-full animate-pulse rounded-sm bg-border" />
          <div className="h-4 w-full animate-pulse rounded-sm bg-border" />
          <div className="h-4 w-1/2 animate-pulse rounded-sm bg-border" />
        </div>
        <div className="h-16 w-full animate-pulse rounded-md bg-border" />
      </div>
    );
  }

  if (state.status === "not-found") {
    return (
      <CenterState
        icon={<Search aria-hidden className="size-7" />}
        title="Listing not found"
        body="This listing may have been removed or the link is incorrect."
      >
        <ButtonLink to="/" className="w-auto min-w-40">
          Back to home
        </ButtonLink>
      </CenterState>
    );
  }

  if (state.status === "error") {
    return (
      <CenterState
        icon={<CircleAlert aria-hidden className="size-7" />}
        title="Couldn't load this listing"
        body="Check your connection and try again."
        danger
      >
        <Button className="w-auto min-w-40" onClick={retry}>
          Retry
        </Button>
      </CenterState>
    );
  }

  const { listing } = state;
  const isOwner = currentUser?.id === listing.seller.id;
  const isFree = listing.price_cents === 0;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 pb-24 lg:pb-6">
      {listing.status === "draft" && (
        <Alert variant="info">This listing is a draft — only you can see it.</Alert>
      )}
      {arrivedFrom.published && <Alert variant="success">Your listing is live!</Alert>}
      {arrivedFrom.saved && <Alert variant="success">Changes saved.</Alert>}

      <PhotoGallery images={listing.images} title={listing.title} />

      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <h1 className="font-display text-2xl font-bold text-text">{listing.title}</h1>
          <span className={`shrink-0 text-xl font-bold ${isFree ? "text-success" : "text-text"}`}>
            {isFree ? "Free" : formatPriceCents(listing.price_cents)}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* The owner sees their listing's status; everyone sees that it's sold. */}
          {(isOwner || listing.status === "sold") && <StatusBadge status={listing.status} />}
          <CategoryChip label={listing.category.name} />
          <span className="text-caption text-text-placeholder">
            Posted {formatRelativeTime(listing.created_at)}
          </span>
        </div>
      </div>

      {listing.description && (
        <p className="text-body whitespace-pre-line text-text-muted">{listing.description}</p>
      )}

      <div className="flex items-center gap-3 rounded-md border border-border p-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-bold text-accent">
          {(listing.seller.display_name ?? "?").slice(0, 1).toUpperCase()}
        </div>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-semibold text-text">
            {listing.seller.display_name ?? "ReNest user"}
          </span>
          <span className="text-caption text-text-placeholder">Verified Creighton student</span>
        </div>
      </div>

      {isOwner && (
        <SellerActions
          listing={listing}
          onChange={(updated) => setState({ status: "loaded", listing: updated })}
        />
      )}

      {/* Reserved for E6's contact button — shown to everyone except the owner. Pinned to
          the bottom on mobile, same pattern as CreateListingPage's Publish bar. */}
      {!isOwner && (
        <div
          data-reserved-for="E6-contact-button"
          className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:hidden"
        />
      )}
    </div>
  );
}
