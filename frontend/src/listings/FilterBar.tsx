import { useEffect, useRef, useState } from "react";
import { FilterChip } from "../components/FilterChip";
import { useCategories } from "./useCategories";

// The home feed's category filter (E5.2, Figma 3:34 desktop and 11:27 mobile). "All", then
// one chip per category in the API's (alphabetical) order. While the categories load, or if
// they fail, only "All" is shown: the feed still works, because the filter comes from the URL.
//
// Pinned to the top of the screen while the feed scrolls (design decision 7). The row scrolls
// sideways when the chips don't fit, with a fade on the right edge while there's more to see.
export function FilterBar({
  selected,
  onSelect,
}: {
  // The category slug in the URL, or null for "All".
  selected: string | null;
  onSelect: (slug: string | null) => void;
}) {
  const categories = useCategories();
  const list = categories.status === "loaded" ? categories.categories : [];
  const rowRef = useRef<HTMLDivElement>(null);
  const [moreToTheRight, setMoreToTheRight] = useState(false);

  // Show the fade only while the row can scroll further right, so it never covers the last
  // chip once you've reached it.
  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    const update = () =>
      // 1px of slack: zoomed pages report fractional scroll positions.
      setMoreToTheRight(row.scrollLeft + row.clientWidth < row.scrollWidth - 1);
    update();
    row.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(row);
    return () => {
      row.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, [list.length]);

  return (
    // -mx-4 on phones: the row scrolls right to the screen edge, while its padding keeps the
    // first chip lined up with the grid. The safe-area padding clears the notch once pinned.
    <div className="sticky top-0 z-10 -mx-4 mb-3 bg-bg pt-[max(0.5rem,env(safe-area-inset-top))] pb-1 lg:mx-0">
      <div className="relative">
        <div
          ref={rowRef}
          role="group"
          aria-label="Filter by category"
          // py-1 (and lg:px-1): room for the focus ring, which overflow would otherwise clip.
          // scroll-pr-12: a chip focused by Tab scrolls fully clear of the fade.
          className="flex gap-2 overflow-x-auto scroll-pr-12 px-4 py-1 [scrollbar-width:none] lg:-mx-1 lg:px-1 [&::-webkit-scrollbar]:hidden"
        >
          <FilterChip label="All" selected={selected === null} onClick={() => onSelect(null)} />
          {list.map((category) => (
            <FilterChip
              key={category.id}
              label={category.name}
              selected={selected === category.slug}
              onClick={() => onSelect(category.slug)}
            />
          ))}
        </div>
        {moreToTheRight && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-linear-to-l from-bg to-transparent"
          />
        )}
      </div>
    </div>
  );
}
