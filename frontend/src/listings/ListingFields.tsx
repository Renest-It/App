import { Alert } from "../components/Alert";
import { CategoryChip } from "../components/CategoryChip";
import { PriceInput } from "../components/PriceInput";
import { Select } from "../components/Select";
import { Textarea } from "../components/Textarea";
import { TextField } from "../components/TextField";
import type { CategoriesState } from "./useCategories";
import { DESCRIPTION_MAX, type FieldErrors } from "./validation";

// What the user has typed, as typed: price is dollars text ("12.50") and categoryId is the
// <select> value. The page converts to the API's shape when it submits.
export type ListingFieldValues = {
  title: string;
  description: string;
  price: string;
  categoryId: string;
};

type ListingFieldsProps = {
  values: ListingFieldValues;
  onChange: (values: ListingFieldValues) => void;
  errors: FieldErrors;
  categories: CategoriesState;
};

// The listing form's text fields (E2.4), shared by the create page and E3.4's edit page so
// the two can't drift apart. Photos are handled separately by each page.
export function ListingFields({ values, onChange, errors, categories }: ListingFieldsProps) {
  function set<K extends keyof ListingFieldValues>(field: K, value: ListingFieldValues[K]) {
    onChange({ ...values, [field]: value });
  }

  const selectedCategory =
    categories.status === "loaded"
      ? categories.categories.find((c) => String(c.id) === values.categoryId)
      : undefined;

  return (
    <div className="flex flex-1 flex-col gap-5">
      {categories.status === "error" && (
        <Alert variant="error">Could not load categories: {categories.message}</Alert>
      )}
      <TextField
        label="Title"
        placeholder="e.g. Mini fridge, 3.2 cu ft"
        value={values.title}
        onChange={(e) => set("title", e.target.value)}
        error={errors.title}
      />
      <Textarea
        label="Description (optional)"
        placeholder="Add details buyers would want to know — condition, dimensions, pickup times…"
        value={values.description}
        onChange={(e) => set("description", e.target.value)}
        maxLength={DESCRIPTION_MAX}
      />
      <div className="flex gap-4">
        <PriceInput
          label="Price"
          placeholder="0.00"
          value={values.price}
          onChange={(e) => set("price", e.target.value)}
          error={errors.price}
        />
        {categories.status === "loaded" ? (
          <Select
            label="Category"
            value={values.categoryId}
            onChange={(e) => set("categoryId", e.target.value)}
            error={errors.category}
          >
            <option value="" disabled>
              Select a category
            </option>
            {categories.categories.map((category) => (
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
  );
}
