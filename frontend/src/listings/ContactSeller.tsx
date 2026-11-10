import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { getSellerContact } from "../api/client";
import type { SellerContact } from "../api/types";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";

type ContactSellerProps = {
  listingId: string;
  listingTitle: string;
};

function errorMessage(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback;
}

// E6.2: fills the slot ListingDetailPage reserves for E6's contact button, for anyone viewing
// a listing who isn't its seller. Two states: a "Contact seller" button, then — once clicked —
// the seller's email as a mailto: link with a copy control. The reveal is per-page-visit: it
// isn't persisted anywhere, so navigating away and back (a fresh mount, since
// ListingDetailPage is keyed by id) shows the button again.
export function ContactSeller({ listingId, listingTitle }: ContactSellerProps) {
  const [contact, setContact] = useState<SellerContact | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function reveal() {
    setLoading(true);
    setError(null);
    try {
      setContact(await getSellerContact(listingId));
    } catch (e) {
      // The listing itself is already rendered above this, so a failure here only affects
      // this control: nothing about the page is lost, and clicking the button retries.
      setError(errorMessage(e, "Couldn't load contact info. Try again."));
    } finally {
      setLoading(false);
    }
  }

  async function copy() {
    if (!contact) return;
    try {
      await navigator.clipboard.writeText(contact.email);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy automatically. Select and copy the email instead.");
    }
  }

  const content = (
    <div className="flex flex-col gap-2">
      {error && <Alert variant="error">{error}</Alert>}
      {/* aria-live: announces the swap from the button to the revealed email, not only a
          visual change (Accessibility AC). */}
      <div aria-live="polite">
        {contact ? (
          <div className="flex items-center gap-2">
            <a
              href={`mailto:${contact.email}?subject=${encodeURIComponent(`ReNest: ${listingTitle}`)}`}
              className={
                "min-w-0 flex-1 truncate rounded-md border border-border bg-surface px-4 py-2.5 " +
                "text-body font-semibold text-accent underline underline-offset-2 " +
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              }
            >
              {contact.email}
            </a>
            <button
              type="button"
              onClick={copy}
              aria-label={copied ? "Email address copied" : "Copy email address"}
              className={
                "flex size-12 shrink-0 items-center justify-center rounded-md border border-border " +
                "bg-surface text-text-muted hover:bg-bg focus-visible:outline-2 " +
                "focus-visible:outline-offset-2 focus-visible:outline-accent"
              }
            >
              {copied ? (
                <Check aria-hidden className="size-4.5 text-success" />
              ) : (
                <Copy aria-hidden className="size-4.5" />
              )}
            </button>
          </div>
        ) : (
          <Button
            loading={loading}
            disabled={loading}
            onClick={reveal}
            className="lg:w-auto! lg:min-w-48!"
          >
            Contact seller
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile: fills the div ListingDetailPage reserves and pins to the bottom. */}
      <div
        data-reserved-for="E6-contact-button"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:hidden"
      >
        {content}
      </div>
      {/* Desktop: this slot isn't reserved by the page, so it sits inline below the seller
          card, the same spot SellerActions occupies for the owner. */}
      <div className="hidden lg:block">{content}</div>
    </>
  );
}