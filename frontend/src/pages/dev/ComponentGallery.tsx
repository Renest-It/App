import { useState } from "react";
import type { Listing } from "../../api/types";
import { Button } from "../../components/Button";
import { CategoryChip } from "../../components/CategoryChip";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { PriceInput } from "../../components/PriceInput";
import { Select } from "../../components/Select";
import { StatusBadge } from "../../components/StatusBadge";
import { Textarea } from "../../components/Textarea";
import { ListingCard } from "../../listings/ListingCard";

const SAMPLE_CATEGORY = { id: 1, name: "Furniture", slug: "furniture" };

const SAMPLE_LISTINGS: Listing[] = [
  {
    id: "1",
    title: "Mini fridge, 3.2 cu ft",
    description: null,
    price_cents: 4000,
    category: SAMPLE_CATEGORY,
    cover_image_url:
      "data:image/svg+xml;utf8," +
      encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="#a8a29e"/></svg>',
      ),
    created_at: new Date().toISOString(),
  },
  {
    id: "2",
    title: "Intro to Psychology textbook, 6th edition",
    description: null,
    price_cents: 0,
    category: { id: 3, name: "Textbooks", slug: "textbooks" },
    cover_image_url: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "3",
    title: "A very long listing title that should truncate instead of wrapping to a second line",
    description: null,
    price_cents: 125000,
    category: { id: 2, name: "Electronics", slug: "electronics" },
    cover_image_url:
      "data:image/svg+xml;utf8," +
      encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="#d6d3d1"/></svg>',
      ),
    created_at: new Date().toISOString(),
  },
];

// Every state of E2.4's and E3.4's shared components, for review before they're used on real
// pages. Dev-only: not linked from the app's nav. See E2.4 (SCRUM-35) and E3.4 (SCRUM-45).
export function ComponentGallery() {
  const [textareaValue, setTextareaValue] = useState("Used for one year, works great.");
  const [selectValue, setSelectValue] = useState("");
  const [priceValue, setPriceValue] = useState("");
  const [openDialog, setOpenDialog] = useState<DialogDemo | null>(null);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-10 p-6">
      <h1 className="font-display text-2xl font-bold text-text">Component Gallery</h1>

      <Section title="Textarea">
        <Textarea label="Description (empty)" value="" onChange={() => {}} maxLength={2000} />
        <Textarea
          label="Description (filled)"
          value={textareaValue}
          onChange={(e) => setTextareaValue(e.target.value)}
          maxLength={2000}
        />
        <Textarea
          label="Description (error)"
          value={"x".repeat(2001)}
          onChange={() => {}}
          maxLength={2000}
          error="Description must be at most 2,000 characters."
        />
        <Textarea
          label="Description (disabled)"
          value="Can't edit this"
          onChange={() => {}}
          disabled
        />
      </Section>

      <Section title="Select">
        <Select
          label="Category (placeholder)"
          value={selectValue}
          onChange={(e) => setSelectValue(e.target.value)}
        >
          <option value="" disabled>
            Select a category
          </option>
          <option value="1">Furniture</option>
          <option value="2">Electronics</option>
        </Select>
        <Select label="Category (selected)" value="2" onChange={() => {}}>
          <option value="1">Furniture</option>
          <option value="2">Electronics</option>
        </Select>
        <Select label="Category (error)" value="" onChange={() => {}} error="Choose a category.">
          <option value="" disabled>
            Select a category
          </option>
          <option value="1">Furniture</option>
        </Select>
        <Select label="Category (disabled)" value="1" onChange={() => {}} disabled>
          <option value="1">Furniture</option>
        </Select>
      </Section>

      <Section title="PriceInput">
        <PriceInput label="Price (empty)" placeholder="0.00" value="" onChange={() => {}} />
        <PriceInput
          label="Price (filled)"
          value={priceValue || "45.00"}
          onChange={(e) => setPriceValue(e.target.value)}
        />
        <PriceInput
          label="Price (error)"
          value="0"
          onChange={() => {}}
          error="Enter a price, or 0 for a free item."
        />
        <PriceInput label="Price (disabled)" value="20.00" onChange={() => {}} disabled />
      </Section>

      <Section title="CategoryChip">
        <div className="flex flex-wrap gap-2">
          <CategoryChip label="Furniture" />
          <CategoryChip label="Electronics" />
          <CategoryChip label="Textbooks" />
        </div>
      </Section>

      <Section title="StatusBadge">
        <div className="flex flex-wrap gap-2">
          <StatusBadge status="draft" />
          <StatusBadge status="active" />
          <StatusBadge status="sold" />
        </div>
      </Section>

      <Section title="ConfirmDialog">
        <div className="grid gap-3 sm:grid-cols-2">
          {DIALOG_DEMOS.map((demo) => (
            <Button key={demo} variant="secondary" onClick={() => setOpenDialog(demo)}>
              {demo}
            </Button>
          ))}
        </div>
        <ConfirmDialog
          open={openDialog === "Default"}
          title="Mark as sold?"
          confirmLabel="Mark as sold"
          onConfirm={() => setOpenDialog(null)}
          onCancel={() => setOpenDialog(null)}
        >
          <strong className="font-semibold text-text">Mini fridge</strong> will be hidden from the
          home feed. You can relist it anytime.
        </ConfirmDialog>
        <ConfirmDialog
          open={openDialog === "Destructive"}
          title="Delete this listing?"
          confirmLabel="Delete listing"
          destructive
          onConfirm={() => setOpenDialog(null)}
          onCancel={() => setOpenDialog(null)}
        >
          <strong className="font-semibold text-text">Mini fridge</strong> and its photos will be
          permanently deleted. This can't be undone.
        </ConfirmDialog>
        <ConfirmDialog
          open={openDialog === "Loading"}
          title="Delete this listing?"
          confirmLabel="Delete listing"
          destructive
          loading
          onConfirm={() => {}}
          onCancel={() => setOpenDialog(null)}
        >
          Stays open while the request runs: Escape and Cancel do nothing. Reload to close.
        </ConfirmDialog>
        <ConfirmDialog
          open={openDialog === "Error"}
          title="Remove this photo?"
          confirmLabel="Remove photo"
          destructive
          error="Could not reach the server. Check your connection."
          onConfirm={() => setOpenDialog(null)}
          onCancel={() => setOpenDialog(null)}
        >
          It's deleted from your listing right away, and can't be undone.
        </ConfirmDialog>
      </Section>

      <Section title="ListingCard">
        {/* With a photo, free with no photo, and a long title — the three states most likely
            to break the layout. Covers both price formats and the no-cover-photo case
            (cover_image_url: null, e.g. a listing from before E2). */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3">
          {SAMPLE_LISTINGS.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      </Section>
    </div>
  );
}

const DIALOG_DEMOS = ["Default", "Destructive", "Loading", "Error"] as const;
type DialogDemo = (typeof DIALOG_DEMOS)[number];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="border-b border-border pb-2 font-display text-lg font-bold text-text">
        {title}
      </h2>
      {children}
    </section>
  );
}
