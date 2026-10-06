import { Link } from "react-router";
import { formatPriceCents } from "../api/format";
import type { Listing } from "../api/types";
import { CategoryChip } from "../components/CategoryChip";

type ListingCardProps = {
  listing: Listing;
};

// A listing on the home grid (E2.7, matches the E2.0 mockup — see CategoryChip's own note that
// the detail page and this card share the same category treatment). Deliberately only depends
// on `Listing`, the plain list-item shape: E4 reuses this same card inside its own grid
// (masonry, filters, pagination), so nothing here assumes it's rendered inside ListPage's grid
// specifically.
export function ListingCard({ listing }: ListingCardProps) {
  const isFree = listing.price_cents === 0;

  return (
    <Link
      to={`/listings/${listing.id}`}
      className="flex flex-col gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      {/* Same aspect ratio as the detail page's gallery (PhotoGallery), so a listing's cover
          photo looks like the same photo whether you're looking at the card or the page. */}
      <div className="aspect-[4/3] w-full overflow-hidden rounded-md bg-border">
        {listing.cover_image_url && (
          <img
            src={listing.cover_image_url}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
          />
        )}
      </div>
      <div className="flex flex-col gap-1">
        <p className="truncate text-sm font-semibold text-text">{listing.title}</p>
        <div className="flex items-center justify-between gap-2">
          <span className={`text-sm font-bold ${isFree ? "text-success" : "text-accent"}`}>
            {isFree ? "Free" : formatPriceCents(listing.price_cents)}
          </span>
          <CategoryChip label={listing.category.name} />
        </div>
      </div>
    </Link>
  );
}
