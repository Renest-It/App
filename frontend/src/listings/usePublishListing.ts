import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  addListingImage,
  createImageUploadUrl,
  createListing,
  publishListing as publishListingApi,
} from "../api/client";
import { processImage, UnsupportedImageError } from "./processImage";

// Matches E2.0's design for the photo thumbnails during publish.
export type PhotoStatus = "waiting" | "uploading" | "done" | "failed";

export type ListingFormData = {
  title: string;
  description: string | null;
  price_cents: number;
  category_id: number;
};

export type PublishPhoto = {
  id: string;
  file: File;
};

const MAX_CONCURRENT_UPLOADS = 2;

// The real publish flow (E2.5, see ADR 0009 and docs/api/listings.md → "The publish flow, end
// to end"): create a draft, upload each photo (resized/re-encoded first), register it, then
// publish. The draft id and each photo's success are remembered across calls, so if `publish`
// is called again with the EXACT SAME form values and photos (a true retry after a failure) it
// only retries what didn't already finish — it never creates a second draft or re-uploads a
// photo that's already done. But if anything changed since the last attempt — a field edited,
// a photo added/removed/reordered — that memory is stale and gets thrown away first: the old
// draft is abandoned (harmless, it's only ever visible to its seller — ADR 0009) and the next
// Publish starts a fresh one with the current values and positions 0..n. Without this, a retry
// after an edit could publish stale field values, leave a removed photo attached, or collide on
// a photo position another photo already holds (caught in review — see PR #26).
export function usePublishListing() {
  const navigate = useNavigate();
  const [photoStatuses, setPhotoStatuses] = useState<Record<string, PhotoStatus>>({});
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const draftIdRef = useRef<string | null>(null);
  const donePhotoIdsRef = useRef<Set<string>>(new Set());
  const unsupportedPhotoIdsRef = useRef<Set<string>>(new Set());
  const lastAttemptKeyRef = useRef<string | null>(null);

  useBeforeUnloadWarning(isPublishing);

  async function publish(form: ListingFormData, photos: PublishPhoto[]) {
    const attemptKey = JSON.stringify({ form, photoIds: photos.map((p) => p.id) });
    if (attemptKey !== lastAttemptKeyRef.current) {
      draftIdRef.current = null;
      donePhotoIdsRef.current = new Set();
      unsupportedPhotoIdsRef.current = new Set();
      lastAttemptKeyRef.current = attemptKey;
    }

    setError(null);
    setIsPublishing(true);
    setPhotoStatuses((current) => {
      const next = { ...current };
      for (const photo of photos) {
        if (!donePhotoIdsRef.current.has(photo.id)) next[photo.id] = "waiting";
      }
      return next;
    });

    let draftId: string;
    try {
      draftId = await ensureDraft(form);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start listing");
      setIsPublishing(false);
      return;
    }

    const pending = photos.filter((photo) => !donePhotoIdsRef.current.has(photo.id));
    await runWithConcurrency(pending, MAX_CONCURRENT_UPLOADS, async (photo) => {
      const position = photos.indexOf(photo);
      const ok = await uploadOnePhoto(draftId, photo, position);
      if (ok) donePhotoIdsRef.current.add(photo.id);
    });

    const allDone = photos.every((photo) => donePhotoIdsRef.current.has(photo.id));
    if (!allDone) {
      const hasUnsupported = photos.some(
        (photo) =>
          !donePhotoIdsRef.current.has(photo.id) && unsupportedPhotoIdsRef.current.has(photo.id),
      );
      setError(
        hasUnsupported
          ? "One of your photos couldn't be processed — HEIC photos from iPhone aren't " +
              "supported yet. Remove it, or convert it to JPEG first, then publish again."
          : "Some photos didn't upload. Try publishing again.",
      );
      setIsPublishing(false);
      return;
    }

    try {
      const published = await publishListingApi(draftId);
      navigate(`/listings/${published.id}`, { state: { justPublished: true } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not publish listing");
      setIsPublishing(false);
    }
  }

  async function ensureDraft(form: ListingFormData): Promise<string> {
    if (draftIdRef.current) return draftIdRef.current;
    const created = await createListing(form);
    draftIdRef.current = created.id;
    return created.id;
  }

  async function uploadOnePhoto(
    draftId: string,
    photo: PublishPhoto,
    position: number,
  ): Promise<boolean> {
    setPhotoStatuses((s) => ({ ...s, [photo.id]: "uploading" }));
    try {
      const processed = await processImage(photo.file);
      const { upload_url, storage_path } = await createImageUploadUrl(draftId, "image/jpeg");
      await putToStorage(upload_url, processed);
      await addListingImage(draftId, { storage_path, position });
      setPhotoStatuses((s) => ({ ...s, [photo.id]: "done" }));
      return true;
    } catch (e) {
      if (e instanceof UnsupportedImageError) unsupportedPhotoIdsRef.current.add(photo.id);
      setPhotoStatuses((s) => ({ ...s, [photo.id]: "failed" }));
      return false;
    }
  }

  return { publish, isPublishing, error, photoStatuses };
}

async function putToStorage(url: string, file: File) {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": file.type },
      body: file,
    });
  } catch {
    throw new Error("Could not upload photo. Check your connection.");
  }
  if (!response.ok) throw new Error("Could not upload photo.");
}

async function runWithConcurrency<T>(items: T[], limit: number, task: (item: T) => Promise<void>) {
  let index = 0;
  async function worker() {
    while (index < items.length) {
      await task(items[index++]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
}

// Warns before leaving the tab while photos are still uploading, so a stray back-swipe or tab
// close doesn't abandon an in-progress publish (the draft and any uploaded photos are still
// safely resumable on return, but the user doesn't know that).
function useBeforeUnloadWarning(active: boolean) {
  useEffect(() => {
    if (!active) return;
    function handler(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active]);
}
