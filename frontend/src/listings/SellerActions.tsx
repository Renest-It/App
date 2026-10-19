import { useState } from "react";
import { useNavigate } from "react-router";
import { deleteListing, markListingSold, markListingUnsold, publishListing } from "../api/client";
import type { ListingDetail } from "../api/types";
import { Alert } from "../components/Alert";
import { Button, ButtonLink } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";

type SellerActionsProps = {
  listing: ListingDetail;
  // Called with the listing as the API returned it after publish, sold, or relist.
  onChange: (listing: ListingDetail) => void;
};

type Dialog = "delete" | "sold" | null;
type Running = "delete" | "sold" | "relist" | "publish" | null;

function errorMessage(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback;
}

// The owner's buttons on the listing detail page (E3.4). Which ones show depends on status:
//   active → Edit, Mark sold, Delete
//   sold   → Relist, Delete (sold listings are frozen; ADR 0010)
//   draft  → Edit, Publish, Delete
// Only rendered for the owner. That's to avoid showing buttons that would fail: the backend
// is what actually refuses everyone else (404 listing_not_found).
export function SellerActions({ listing, onChange }: SellerActionsProps) {
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [running, setRunning] = useState<Running>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function run(
    action: Exclude<Running, null>,
    call: () => Promise<ListingDetail>,
    success: string,
  ) {
    setRunning(action);
    setError(null);
    setNotice(null);
    try {
      onChange(await call());
      setDialog(null);
      setNotice(success);
    } catch (e) {
      setError(errorMessage(e, "Something went wrong. Try again."));
    } finally {
      setRunning(null);
    }
  }

  async function confirmDelete() {
    setRunning("delete");
    setError(null);
    try {
      await deleteListing(listing.id);
      navigate("/account/listings", { replace: true });
    } catch (e) {
      setError(errorMessage(e, "Could not delete this listing. Try again."));
      setRunning(null);
    }
  }

  function openDialog(which: Exclude<Dialog, null>) {
    setError(null);
    setNotice(null);
    setDialog(which);
  }

  function closeDialog() {
    setDialog(null);
    setError(null);
  }

  const busy = running !== null;
  const editLink = (
    <ButtonLink to={`/listings/${listing.id}/edit`} variant="secondary">
      Edit listing
    </ButtonLink>
  );
  const deleteButton = (
    <Button variant="danger" disabled={busy} onClick={() => openDialog("delete")}>
      Delete
    </Button>
  );

  return (
    <section aria-label="Manage your listing" className="flex flex-col gap-3">
      {notice && <Alert variant="success">{notice}</Alert>}
      {/* Errors from the dialogs show inside them; this is for the buttons with no dialog. */}
      {error && dialog === null && <Alert variant="error">{error}</Alert>}

      <div className="grid gap-3 sm:auto-cols-fr sm:grid-flow-col">
        {listing.status === "active" && (
          <>
            {editLink}
            <Button disabled={busy} onClick={() => openDialog("sold")}>
              Mark as sold
            </Button>
            {deleteButton}
          </>
        )}
        {listing.status === "sold" && (
          <>
            <Button
              loading={running === "relist"}
              disabled={busy}
              onClick={() =>
                run("relist", () => markListingUnsold(listing.id), "Your listing is back on sale.")
              }
            >
              Relist
            </Button>
            {deleteButton}
          </>
        )}
        {listing.status === "draft" && (
          <>
            {editLink}
            <Button
              loading={running === "publish"}
              disabled={busy}
              onClick={() =>
                run("publish", () => publishListing(listing.id), "Your listing is live!")
              }
            >
              Publish
            </Button>
            {deleteButton}
          </>
        )}
      </div>

      <ConfirmDialog
        open={dialog === "sold"}
        title="Mark as sold?"
        confirmLabel="Mark as sold"
        loading={running === "sold"}
        error={error}
        onConfirm={() =>
          run("sold", () => markListingSold(listing.id), "Marked as sold. Nice work!")
        }
        onCancel={closeDialog}
      >
        <strong className="font-semibold text-text">{listing.title}</strong> will be hidden from the
        home feed. You can relist it anytime.
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog === "delete"}
        title="Delete this listing?"
        confirmLabel="Delete listing"
        destructive
        loading={running === "delete"}
        error={error}
        onConfirm={confirmDelete}
        onCancel={closeDialog}
      >
        <strong className="font-semibold text-text">{listing.title}</strong> and its photos will be
        permanently deleted. This can't be undone.
      </ConfirmDialog>
    </section>
  );
}
