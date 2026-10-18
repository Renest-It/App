import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  addListingImage,
  createImageUploadUrl,
  deleteListingImage,
  getListing,
} from "../api/client";
import type { ListingDetail } from "../api/types";
import { processImage, UnsupportedImageError } from "./processImage";
import { putToStorage } from "./usePublishListing";
import { MAX_PHOTOS } from "./validation";

// A photo picked on the edit page that isn't on the listing yet.
type PendingPhoto = {
  id: string;
  file: File;
  previewUrl: string;
  status: "uploading" | "failed";
};

// Photo editing on an existing listing (E3.4, docs/api/listings.md → "Editing photos on a
// published listing"). Unlike the create page, changes are saved right away rather than with
// the form: an added photo is resized (E2.5's processImage, unchanged), uploaded, and recorded
// at the next free position; a removed one is deleted and the listing re-fetched, since the
// photos after it move down a position.
//
// Uploads run one at a time, so each takes the next position without racing another. Removing
// is disabled while anything is uploading, so a position can't shift under an upload either.
export function useEditPhotos(
  listing: ListingDetail,
  setListing: Dispatch<SetStateAction<ListingDetail>>,
) {
  const [pending, setPending] = useState<PendingPhoto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const queueRef = useRef<Promise<void>>(Promise.resolve());

  // The position the next upload records itself at: the number of photos the listing has.
  const nextPositionRef = useRef(listing.images.length);
  useEffect(() => {
    nextPositionRef.current = listing.images.length;
  }, [listing.images]);

  // Revoke the remaining previews on unmount (same pattern as usePhotoPicker).
  const pendingRef = useRef(pending);
  useEffect(() => {
    pendingRef.current = pending;
  }, [pending]);
  useEffect(() => {
    return () => {
      for (const photo of pendingRef.current) URL.revokeObjectURL(photo.previewUrl);
    };
  }, []);

  async function upload(photo: PendingPhoto) {
    try {
      const processed = await processImage(photo.file);
      const { upload_url, storage_path } = await createImageUploadUrl(listing.id, "image/jpeg");
      await putToStorage(upload_url, processed);
      const image = await addListingImage(listing.id, {
        storage_path,
        position: nextPositionRef.current,
      });
      nextPositionRef.current += 1;
      setListing((current) => ({ ...current, images: [...current.images, image] }));
      URL.revokeObjectURL(photo.previewUrl);
      setPending((current) => current.filter((p) => p.id !== photo.id));
    } catch (e) {
      setPending((current) =>
        current.map((p) => (p.id === photo.id ? { ...p, status: "failed" } : p)),
      );
      setError(
        e instanceof UnsupportedImageError
          ? "One of your photos couldn't be processed — HEIC photos from iPhone aren't " +
              "supported yet. Remove it, or convert it to JPEG first."
          : "A photo didn't upload. Remove it and try adding it again.",
      );
    }
  }

  function addPhotos(files: File[]) {
    setError(null);
    const room = MAX_PHOTOS - listing.images.length - pending.length;
    const added: PendingPhoto[] = files.slice(0, Math.max(room, 0)).map((file) => ({
      id: crypto.randomUUID(),
      file,
      previewUrl: URL.createObjectURL(file),
      status: "uploading",
    }));
    setPending((current) => [...current, ...added]);
    for (const photo of added) {
      queueRef.current = queueRef.current.then(() => upload(photo));
    }
  }

  // Only for a pending photo that failed: it was never saved, so there's nothing to confirm.
  function discardPending(id: string) {
    setPending((current) => {
      const photo = current.find((p) => p.id === id);
      if (photo) URL.revokeObjectURL(photo.previewUrl);
      return current.filter((p) => p.id !== id);
    });
  }

  // For a saved photo, after the user confirms. Throws so the confirm dialog can show why.
  async function removeSavedPhoto(imageId: string) {
    setError(null);
    await deleteListingImage(listing.id, imageId);
    setListing(await getListing(listing.id));
  }

  return {
    pending,
    isUploading: pending.some((p) => p.status === "uploading"),
    error,
    addPhotos,
    discardPending,
    removeSavedPhoto,
  };
}
