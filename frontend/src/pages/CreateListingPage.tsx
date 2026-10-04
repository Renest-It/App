import { useEffect, useState, type FormEvent } from "react";
import { getCategories } from "../api/client";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { CategoryChip } from "../components/CategoryChip";
import { PriceInput } from "../components/PriceInput";
import { Select } from "../components/Select";
import { Textarea } from "../components/Textarea";
import { TextField } from "../components/TextField";
import type { Category } from "../api/types";
import { PhotoPicker } from "../listings/PhotoPicker";
import { usePhotoPicker } from "../listings/usePhotoPicker";
import { usePublishListing } from "../listings/usePublishListing";
import {
  DESCRIPTION_MAX,
  parsePriceCents,
  validateListingForm,
  type FieldErrors,
} from "../listings/validation";

type CategoriesState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; categories: Category[] };

// The page layout, form fields, photo picker, and publish flow for creating a listing
// (E2.4 + E2.5). Validates client-side against the same rules as the backend
// (docs/api/listings.md), then creates the draft, uploads each photo, and publishes it
// (usePublishListing — see ADR 0009). E2.7 wires this page into the app's real /sell route.
export function CreateListingPage() {
  const [categoriesState, setCategoriesState] = useState<CategoriesState>({ status: "loading" });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const { photos, addPhotos, removePhoto } = usePhotoPicker();
  const { publish, isPublishing, error: publishError, photoStatuses } = usePublishListing();

  useEffect(() => {
    getCategories()
      .then((categories) => setCategoriesState({ status: "loaded", categories }))
      .catch((e) =>
        setCategoriesState({
          status: "error",
          message: e instanceof Error ? e.message : "Could not load categories",
        }),
      );
  }, []);

  const errors: FieldErrors = attemptedSubmit
    ? validateListingForm({ title, price, categoryId, photoCount: photos.length })
    : {};
  const selectedCategory =
    categoriesState.status === "loaded"
      ? categoriesState.categories.find((c) => String(c.id) === categoryId)
      : undefined;

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

      {categoriesState.status === "error" && (
        <Alert variant="error">Could not load categories: {categoriesState.message}</Alert>
      )}

      <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8">
        {/* Desktop: fields on the right (lg:flex-row-reverse above puts this first visually). */}
        <div className="flex flex-1 flex-col gap-5">
          <TextField
            label="Title"
            placeholder="e.g. Mini fridge, 3.2 cu ft"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            error={errors.title}
          />
          <Textarea
            label="Description (optional)"
            placeholder="Add details buyers would want to know — condition, dimensions, pickup times…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={DESCRIPTION_MAX}
          />
          <div className="flex gap-4">
            <PriceInput
              label="Price"
              placeholder="0.00"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              error={errors.price}
            />
            {categoriesState.status === "loaded" ? (
              <Select
                label="Category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                error={errors.category}
              >
                <option value="" disabled>
                  Select a category
                </option>
                {categoriesState.categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            ) : (
              <div className="flex w-full flex-col gap-2">
                <span className="text-sm font-semibold text-text">Category</span>
                <div className="h-12 w-full animate-pulse rounded-md bg-border" />
              </div>
            )}
          </div>
          {selectedCategory && <CategoryChip label={selectedCategory.name} />}
        </div>

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
