import { Camera, X } from "lucide-react";
import { useId, useRef } from "react";
import { MAX_PHOTOS } from "./validation";
import type { PickedPhoto } from "./usePhotoPicker";

type PhotoPickerProps = {
  photos: PickedPhoto[];
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
  error?: string;
};

// Display only: picks files and shows thumbnails. E2.5 resizes, re-encodes, and uploads them.
export function PhotoPicker({ photos, onAdd, onRemove, error }: PhotoPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const atMax = photos.length >= MAX_PHOTOS;

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    // Copy to a plain array *before* resetting value below. FileList is a live object tied
    // to the input — resetting value clears it too, and React may not read these files until
    // after this handler returns (e.g. when batched with another update elsewhere on the
    // page), so a lazy Array.from(event.target.files) done later can see an empty list.
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) {
      onAdd(files);
    }
    // Reset so picking the exact same file again still fires onChange.
    event.target.value = "";
  }

  return (
    <div className="flex w-full flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-semibold text-text">
        Photos (Up to {MAX_PHOTOS})
      </label>
      <div
        className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-3"
        aria-describedby={error ? errorId : undefined}
      >
        {photos.map((photo, index) => (
          <div key={photo.id} className="relative aspect-square overflow-hidden rounded-md">
            <img
              src={photo.previewUrl}
              alt={index === 0 ? "Cover photo" : `Photo ${index + 1}`}
              className="h-full w-full object-cover"
            />
            {index === 0 && (
              <span className="absolute top-1 left-1 rounded-sm bg-text/70 px-1.5 py-0.5 text-xs font-semibold text-surface">
                Cover
              </span>
            )}
            <button
              type="button"
              onClick={() => onRemove(photo.id)}
              aria-label={`Remove photo ${index + 1}`}
              className={
                "absolute top-1 right-1 flex size-11 items-center justify-center rounded-full " +
                "bg-text/70 text-surface focus-visible:outline-2 focus-visible:outline-offset-2 " +
                "focus-visible:outline-accent"
              }
            >
              <X aria-hidden className="size-4" />
            </button>
          </div>
        ))}
        {!atMax && (
          <label
            htmlFor={inputId}
            className={
              "flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 " +
              "rounded-md border-[1.5px] border-dashed border-border bg-surface text-text-placeholder " +
              "hover:border-accent hover:text-accent"
            }
          >
            <Camera aria-hidden className="size-6" />
            <span className="text-xs font-medium">Add photo</span>
          </label>
        )}
      </div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept="image/*"
        multiple
        onChange={handleChange}
        className="sr-only"
      />
      <span className="text-caption text-text-placeholder">
        {photos.length}/{MAX_PHOTOS} photos
      </span>
      {error && (
        <p id={errorId} className="text-caption font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
