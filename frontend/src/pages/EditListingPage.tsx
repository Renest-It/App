import { CircleAlert, Lock, Search } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useBlocker, useNavigate, useParams } from "react-router";
import { ApiError, getListing, updateListing } from "../api/client";
import type { ListingDetail, ListingUpdate } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { Button, ButtonLink } from "../components/Button";
import { CenterState } from "../components/CenterState";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { StatusBadge } from "../components/StatusBadge";
import { ListingFields, type ListingFieldValues } from "../listings/ListingFields";
import { PhotoPicker } from "../listings/PhotoPicker";
import { useCategories } from "../listings/useCategories";
import { useEditPhotos } from "../listings/useEditPhotos";
import { useBeforeUnloadWarning } from "../listings/usePublishListing";
import {
  centsToPriceInput,
  parsePriceCents,
  validateListingForm,
  type FieldErrors,
} from "../listings/validation";

type LoadState =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error" }
  | { status: "loaded"; listing: ListingDetail };

// The edit page for a draft or active listing (E3.4), at /listings/:id/edit. Reuses E2.4's
// form fields and validation, and saves only the fields that changed (PATCH). Photos are
// saved as they're added or removed (useEditPhotos). Sold listings can't be edited (the API
// returns 409 listing_sold), so this page says so instead of showing the form.
export function EditListingPage() {
  const { id } = useParams<{ id: string }>();
  return <EditListingLoader key={id} id={id!} />;
}

function EditListingLoader({ id }: { id: string }) {
  const { currentUser, currentUserLoading } = useAuth();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getListing(id)
      .then((listing) => {
        if (!cancelled) setState({ status: "loaded", listing });
      })
      .catch((e) => {
        if (cancelled) return;
        setState(
          e instanceof ApiError && e.code === "listing_not_found"
            ? { status: "not-found" }
            : { status: "error" },
        );
      });
    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  if (state.status === "loading" || (state.status === "loaded" && currentUserLoading)) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6" aria-busy>
        <div className="h-8 w-1/3 animate-pulse rounded-sm bg-border" />
        <div className="h-12 w-full animate-pulse rounded-md bg-border" />
        <div className="h-28 w-full animate-pulse rounded-md bg-border" />
        <div className="h-12 w-full animate-pulse rounded-md bg-border" />
      </div>
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
        <Button
          className="w-auto min-w-40"
          onClick={() => {
            setState({ status: "loading" });
            setAttempt((a) => a + 1);
          }}
        >
          Retry
        </Button>
      </CenterState>
    );
  }

  // Someone else's listing looks exactly like a missing one, as it does in the API (ADR 0010).
  if (state.status === "not-found" || state.listing.seller.id !== currentUser?.id) {
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

  if (state.listing.status === "sold") {
    return (
      <CenterState
        icon={<Lock aria-hidden className="size-7" />}
        title="Sold listings can't be edited"
        body="Relist it first if you need to change something."
      >
        <ButtonLink to={`/listings/${id}`} className="w-auto min-w-40">
          Back to listing
        </ButtonLink>
      </CenterState>
    );
  }

  return <EditListingForm initialListing={state.listing} />;
}

function initialValues(listing: ListingDetail): ListingFieldValues {
  return {
    title: listing.title,
    description: listing.description ?? "",
    price: centsToPriceInput(listing.price_cents),
    categoryId: String(listing.category.id),
  };
}

// The fields whose (trimmed) value differs from what's saved: both the PATCH body and how the
// page knows there are unsaved changes. An invalid price counts as a change.
function changedFields(values: ListingFieldValues, listing: ListingDetail) {
  const changes: Partial<Record<keyof ListingUpdate, unknown>> = {};
  const title = values.title.trim();
  const description = values.description.trim() || null;
  const priceCents = parsePriceCents(values.price);
  const categoryId = Number(values.categoryId);
  if (title !== listing.title) changes.title = title;
  if (description !== listing.description) changes.description = description;
  if (priceCents !== listing.price_cents) changes.price_cents = priceCents;
  if (categoryId !== listing.category.id) changes.category_id = categoryId;
  return changes;
}

function EditListingForm({ initialListing }: { initialListing: ListingDetail }) {
  const navigate = useNavigate();
  const categories = useCategories();
  const [listing, setListing] = useState(initialListing);
  const [values, setValues] = useState(() => initialValues(initialListing));
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const photos = useEditPhotos(listing, setListing);
  const [photoToRemove, setPhotoToRemove] = useState<string | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const detailPath = `/listings/${listing.id}`;
  const isDirty = Object.keys(changedFields(values, listing)).length > 0;
  const hasUnsavedWork = isDirty || photos.isUploading;

  // Set right before navigating away after a successful save, so the unsaved-changes prompt
  // doesn't stop it.
  const leavingRef = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      !leavingRef.current && hasUnsavedWork && currentLocation.pathname !== nextLocation.pathname,
  );
  useBeforeUnloadWarning(hasUnsavedWork);

  const errors: FieldErrors = attemptedSubmit ? validateListingForm(values) : {};

  // The last photo on a published listing can't be removed (the API refuses with
  // 422 last_photo_required), so its remove button is hidden and the hint says why.
  const lastPhotoLocked = listing.status === "active" && listing.images.length === 1;
  const savedPhotoIds = new Set(listing.images.map((i) => i.id));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAttemptedSubmit(true);
    if (Object.keys(validateListingForm(values)).length > 0) return;

    const changes = changedFields(values, listing) as ListingUpdate;
    if (Object.keys(changes).length === 0) {
      navigate(detailPath);
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    try {
      await updateListing(listing.id, changes);
      leavingRef.current = true;
      navigate(detailPath, { state: { justSaved: true } });
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not save your changes. Try again.");
      setIsSaving(false);
    }
  }

  function handleRemove(id: string) {
    if (savedPhotoIds.has(id)) {
      setRemoveError(null);
      setPhotoToRemove(id);
    } else {
      photos.discardPending(id);
    }
  }

  async function confirmRemove() {
    if (!photoToRemove) return;
    setIsRemoving(true);
    setRemoveError(null);
    try {
      await photos.removeSavedPhoto(photoToRemove);
      setPhotoToRemove(null);
    } catch (e) {
      setRemoveError(e instanceof Error ? e.message : "Could not remove this photo. Try again.");
    } finally {
      setIsRemoving(false);
    }
  }

  const removingCover = listing.images[0]?.id === photoToRemove;

  return (
    // Same layout as CreateListingPage: pb reserves room for the pinned save bar on mobile.
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex w-full max-w-4xl flex-col gap-6 pb-28 lg:pb-6"
    >
      <div className="flex items-center gap-3">
        <h1 className="font-display text-2xl font-bold text-text">Edit listing</h1>
        <StatusBadge status={listing.status} />
      </div>

      <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8">
        <ListingFields
          values={values}
          onChange={setValues}
          errors={errors}
          categories={categories}
        />

        <div className="flex flex-col gap-3 lg:w-80 lg:shrink-0">
          <PhotoPicker
            photos={[
              ...listing.images.map((image) => ({ id: image.id, previewUrl: image.url })),
              ...photos.pending,
            ]}
            statuses={Object.fromEntries(photos.pending.map((p) => [p.id, p.status]))}
            onAdd={photos.addPhotos}
            onRemove={handleRemove}
            canRemove={(id) =>
              savedPhotoIds.has(id) ? !photos.isUploading && !lastPhotoLocked : true
            }
            hint={
              lastPhotoLocked
                ? "A published listing needs at least one photo. Add another to replace this one."
                : "Photo changes are saved right away."
            }
          />
          {photos.error && <Alert variant="error">{photos.error}</Alert>}
        </div>
      </div>

      {saveError && <Alert variant="error">{saveError}</Alert>}

      {/* Mobile: pinned above the home indicator. Desktop: inline at the end of the form. */}
      <div
        className={
          "fixed inset-x-0 bottom-0 z-10 flex gap-3 border-t border-border bg-surface px-4 pt-3 " +
          "pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:static lg:border-0 lg:bg-transparent lg:p-0"
        }
      >
        <ButtonLink to={detailPath} variant="secondary" className="lg:max-w-40">
          Cancel
        </ButtonLink>
        <Button
          type="submit"
          loading={isSaving}
          disabled={photos.isUploading}
          className="lg:max-w-xs"
        >
          Save changes
        </Button>
      </div>

      <ConfirmDialog
        open={photoToRemove !== null}
        title="Remove this photo?"
        confirmLabel="Remove photo"
        destructive
        loading={isRemoving}
        error={removeError}
        onConfirm={confirmRemove}
        onCancel={() => setPhotoToRemove(null)}
      >
        It's deleted from your listing right away, and can't be undone.
        {removingCover && " The next photo becomes the cover."}
      </ConfirmDialog>

      <ConfirmDialog
        open={blocker.state === "blocked"}
        title="Leave without saving?"
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        destructive
        onConfirm={() => blocker.proceed?.()}
        onCancel={() => blocker.reset?.()}
      >
        {photos.isUploading
          ? "Photos are still uploading, and your other changes haven't been saved."
          : "Your changes to this listing haven't been saved."}
      </ConfirmDialog>
    </form>
  );
}
