import { useState, type FormEvent } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { ListingFields, type ListingFieldValues } from "../listings/ListingFields";
import { PhotoPicker } from "../listings/PhotoPicker";
import { useCategories } from "../listings/useCategories";
import { usePhotoPicker } from "../listings/usePhotoPicker";
import { usePublishListing } from "../listings/usePublishListing";
import { parsePriceCents, validateListingForm, type FieldErrors } from "../listings/validation";

// The page layout, form fields, photo picker, and publish flow for creating a listing
// (E2.4 + E2.5). Validates client-side against the same rules as the backend
// (docs/api/listings.md), then creates the draft, uploads each photo, and publishes it
// (usePublishListing — see ADR 0009). E2.7 wires this page into the app's real /sell route.
export function CreateListingPage() {
  const categories = useCategories();
  const [values, setValues] = useState<ListingFieldValues>({
    title: "",
    description: "",
    price: "",
    categoryId: "",
  });
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const { photos, addPhotos, removePhoto } = usePhotoPicker();
  const { publish, isPublishing, error: publishError, photoStatuses } = usePublishListing();
  const { title, description, price, categoryId } = values;

  const errors: FieldErrors = attemptedSubmit
    ? validateListingForm({ title, price, categoryId, photoCount: photos.length })
    : {};

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAttemptedSubmit(true);

    const fieldErrors = validateListingForm({
      title,
      price,
      categoryId,
      photoCount: photos.length,
    });
    if (Object.keys(fieldErrors).length > 0) return;

    const priceCents = parsePriceCents(price);
    if (priceCents === null || !categoryId) return; // unreachable: validateListingForm covers both

    void publish(
      {
        title: title.trim(),
        description: description.trim() || null,
        price_cents: priceCents,
        category_id: Number(categoryId),
      },
      photos.map((p) => ({ id: p.id, file: p.file })),
    );
  }

  return (
    // pb reserves room for the pinned Publish bar on mobile so the last field is never hidden
    // behind it. Desktop scrolls normally; the button sits in the form's own flow there.
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex w-full max-w-4xl flex-col gap-6 pb-28 lg:pb-6"
    >
      <h1 className="font-display text-2xl font-bold text-text">Sell an item</h1>

      <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8">
        {/* Desktop: fields on the right (lg:flex-row-reverse above puts this first visually). */}
        <ListingFields
          values={values}
          onChange={setValues}
          errors={errors}
          categories={categories}
        />

        {/* Desktop: photos on the left. */}
        <div className="lg:w-80 lg:shrink-0">
          <PhotoPicker
            photos={photos}
            onAdd={addPhotos}
            onRemove={removePhoto}
            statuses={photoStatuses}
            disabled={isPublishing}
            error={errors.photos}
          />
        </div>
      </div>

      {publishError && <Alert variant="error">{publishError}</Alert>}

      {/* Mobile: pinned above the home indicator. Desktop: inline at the end of the form. */}
      <div
        className={
          "fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface px-4 pt-3 " +
          "pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:static lg:border-0 lg:bg-transparent lg:p-0"
        }
      >
        <Button type="submit" loading={isPublishing} className="lg:max-w-xs">
          Publish listing
        </Button>
      </div>
    </form>
  );
}
