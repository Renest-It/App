import { LoaderCircle } from "lucide-react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import type { FeedStatus } from "./useFeed";

type FeedFooterProps = {
  status: FeedStatus;
  onLoadMore: () => void;
  onRetry: () => void;
};

// The single slot under the feed's grid (E4.0 / docs/design/feed-states.md, decision 1): it
// shows exactly one state, at a fixed height, so the cards above never move when it changes.
// aria-live: screen readers hear the change without focus moving.
export function FeedFooter({ status, onLoadMore, onRetry }: FeedFooterProps) {
  return (
    <div aria-live="polite" className="flex h-32 items-center justify-center lg:h-20">
      {status === "idle" && (
        <Button variant="secondary" className="w-auto min-w-40" onClick={onLoadMore}>
          Load more
        </Button>
      )}

      {status === "loading-more" && (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <LoaderCircle aria-hidden className="size-4.5 animate-spin" />
          Loading more…
        </p>
      )}

      {status === "more-error" && (
        // Stacked on mobile, side by side from sm (decision 6).
        <div className="flex w-full max-w-md flex-col items-center gap-3 sm:flex-row">
          <Alert>Couldn't load more listings.</Alert>
          <Button variant="secondary" className="w-auto min-w-40 shrink-0" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}

      {status === "done" && (
        <p className="flex items-center gap-3 text-center text-sm text-text-muted">
          <span aria-hidden className="h-px w-8 shrink-0 bg-border" />
          You've seen everything — check back soon for new listings.
          <span aria-hidden className="h-px w-8 shrink-0 bg-border" />
        </p>
      )}
    </div>
  );
}
