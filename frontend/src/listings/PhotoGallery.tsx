import { useRef, useState } from "react";
import type { ListingImage } from "../api/types";

type PhotoGalleryProps = {
  images: ListingImage[];
  title: string;
};

// Mobile: a full-width swipeable strip using CSS scroll-snap (no carousel library) with dot
// indicators. Desktop: one main image with a row of clickable thumbnails. Both share the same
// active index. Every photo after the first loads lazily — only the one shown first is eager.
export function PhotoGallery({ images, title }: PhotoGalleryProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const stripRef = useRef<HTMLDivElement>(null);

  if (images.length === 0) {
    return <div className="aspect-[4/3] w-full rounded-md bg-border" aria-hidden />;
  }

  function altFor(index: number) {
    return `${title}, photo ${index + 1}`;
  }

  // Mobile: update the active dot as the user swipes, from the strip's own scroll position.
  function handleScroll() {
    const strip = stripRef.current;
    if (!strip) return;
    const index = Math.round(strip.scrollLeft / strip.clientWidth);
    setActiveIndex(Math.min(Math.max(index, 0), images.length - 1));
  }

  // Desktop: clicking a thumbnail swaps the main image.
  function selectImage(index: number) {
    setActiveIndex(index);
  }

  if (images.length === 1) {
    return (
      <div className="aspect-[4/3] w-full overflow-hidden rounded-md bg-border">
        <img
          src={images[0].url}
          alt={altFor(0)}
          className="h-full w-full object-cover"
          loading="eager"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Mobile: swipeable strip + dots. */}
      <div className="lg:hidden">
        <div
          ref={stripRef}
          onScroll={handleScroll}
          className="flex aspect-[4/3] w-full snap-x snap-mandatory overflow-x-auto rounded-md"
        >
          {images.map((image, index) => (
            <img
              key={image.id}
              src={image.url}
              alt={altFor(index)}
              loading={index === 0 ? "eager" : "lazy"}
              className="h-full w-full shrink-0 snap-start object-cover"
            />
          ))}
        </div>
        <div className="mt-2 flex justify-center gap-1.5">
          {images.map((image, index) => (
            <span
              key={image.id}
              aria-hidden
              className={`size-1.5 rounded-full ${index === activeIndex ? "bg-accent" : "bg-border"}`}
            />
          ))}
        </div>
      </div>

      {/* Desktop: one main image + thumbnail row. */}
      <div className="hidden lg:flex lg:flex-col lg:gap-2">
        <div className="aspect-[4/3] w-full overflow-hidden rounded-md bg-border">
          <img
            src={images[activeIndex].url}
            alt={altFor(activeIndex)}
            loading="eager"
            className="h-full w-full object-cover"
          />
        </div>
        <div className="flex gap-2">
          {images.map((image, index) => (
            <button
              key={image.id}
              type="button"
              onClick={() => selectImage(index)}
              aria-label={`Show photo ${index + 1}`}
              aria-current={index === activeIndex}
              className={
                "size-14 shrink-0 overflow-hidden rounded-sm focus-visible:outline-2 " +
                "focus-visible:outline-offset-2 focus-visible:outline-accent " +
                (index === activeIndex ? "outline-2 outline-offset-1 outline-accent" : "")
              }
            >
              <img
                src={image.url}
                alt=""
                loading={index === 0 ? "eager" : "lazy"}
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
