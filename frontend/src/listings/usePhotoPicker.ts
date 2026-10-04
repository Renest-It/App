import { useEffect, useRef, useState } from "react";
import { MAX_PHOTOS } from "./validation";

export type PickedPhoto = {
  id: string;
  file: File;
  // A temporary local URL for the thumbnail. Revoked when the photo is removed or the page
  // unmounts, so previews don't leak memory (E2.4 acceptance criteria).
  previewUrl: string;
};

// Display-only photo picker state: which files are selected and their thumbnail previews.
// Resizing, re-encoding, and actually uploading the files is E2.5's job — this hook only
// tracks what the user picked so the page can show it.
export function usePhotoPicker() {
  const [photos, setPhotos] = useState<PickedPhoto[]>([]);
  // Mirrors `photos` for the unmount cleanup below, which must not depend on `photos` itself
  // (that would revoke every preview on every render instead of only on unmount). Refs can't
  // be written during render, so this runs as its own effect instead.
  const photosRef = useRef(photos);
  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);

  useEffect(() => {
    return () => {
      for (const photo of photosRef.current) {
        URL.revokeObjectURL(photo.previewUrl);
      }
    };
  }, []);

  function addPhotos(files: File[]) {
    // `files` must already be a plain array, not a live FileList — see PhotoPicker's
    // handleChange for why reading one lazily in here is a bug.
    setPhotos((current) => {
      const room = MAX_PHOTOS - current.length;
      if (room <= 0) return current;
      const toAdd = files
        .slice(0, room)
        .map((file) => ({ id: crypto.randomUUID(), file, previewUrl: URL.createObjectURL(file) }));
      return [...current, ...toAdd];
    });
  }

  function removePhoto(id: string) {
    setPhotos((current) => {
      const photo = current.find((p) => p.id === id);
      if (photo) URL.revokeObjectURL(photo.previewUrl);
      return current.filter((p) => p.id !== id);
    });
  }

  return { photos, addPhotos, removePhoto, atMax: photos.length >= MAX_PHOTOS };
}
