import { useEffect, useState } from "react";
import { PriceInput } from "../components/PriceInput";
import { PRICE_MAX_CENTS, centsToPriceInput, parsePriceCents } from "./validation";

// The price-range half of the feed filter (E5.4). Values commit on blur/Enter, not on every
// keystroke, so typing "1" then "2" never sends two separate requests or URL updates — only
// the finished number does. Reuses PriceInput and the dollars<->cents helpers from the listing
// form (validation.ts) rather than a second implementation, per the ticket's design decision.
export function PriceRangeFilter({
  min,
  max,
  onApply,
}: {
  // Cents, or undefined if that end isn't set. Comes from the URL (ListPage).
  min: number | undefined;
  max: number | undefined;
  // Called only when the committed values actually change, and only once both are valid.
  onApply: (min: number | undefined, max: number | undefined) => void;
}) {
  const [minText, setMinText] = useState(min === undefined ? "" : centsToPriceInput(min));
  const [maxText, setMaxText] = useState(max === undefined ? "" : centsToPriceInput(max));
  const [error, setError] = useState<string | undefined>(undefined);

  // Clearing the filter elsewhere (e.g. "Clear filter" in an empty state) should empty these
  // too, not leave stale text the URL no longer matches.
  useEffect(() => {
    setMinText(min === undefined ? "" : centsToPriceInput(min));
  }, [min]);
  useEffect(() => {
    setMaxText(max === undefined ? "" : centsToPriceInput(max));
  }, [max]);

  function commit() {
    const minRaw = minText.trim();
    const maxRaw = maxText.trim();
    const minParsed = minRaw === "" ? undefined : parsePriceCents(minRaw);
    const maxParsed = maxRaw === "" ? undefined : parsePriceCents(maxRaw);

    if (minParsed === null || maxParsed === null) {
      setError("Enter a price, like 10 or 10.50.");
      return;
    }
    const minCents = minParsed;
    const maxCents = maxParsed;

    if ((minCents ?? 0) > PRICE_MAX_CENTS || (maxCents ?? 0) > PRICE_MAX_CENTS) {
      setError("Enter a price under $10,000.");
      return;
    }
    if (minCents !== undefined && maxCents !== undefined && minCents > maxCents) {
      setError("The minimum can't be more than the maximum.");
      return;
    }

    setError(undefined);
    if (minCents !== min || maxCents !== max) onApply(minCents, maxCents);
  }

  return (
    <div className="mb-3 flex flex-col gap-2">
      <div className="flex items-end gap-3">
        <PriceInput
          label="Min price"
          placeholder="0"
          value={minText}
          onChange={(e) => setMinText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
        <span aria-hidden className="mb-3 text-text-muted">
          –
        </span>
        <PriceInput
          label="Max price"
          placeholder="Any"
          value={maxText}
          onChange={(e) => setMaxText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-caption font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}