import { useEffect, useId, useRef, type ReactNode } from "react";
import { Alert } from "./Alert";
import { Button } from "./Button";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  // Red confirm button, for actions that can't be undone (delete a listing, remove a photo).
  destructive?: boolean;
  // While the confirmed action runs: spinner on confirm, and the dialog can't be dismissed.
  loading?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
};

const FOCUSABLE = "button:not(:disabled), [href], input, select, textarea, [tabindex]";

// A modal "are you sure?" dialog (E3.4). Built on the native <dialog> element: showModal()
// makes the rest of the page inert and Escape closes it. On top of that, Tab wraps around
// inside the dialog, and focus goes back to whatever opened it when it closes.
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = false,
  loading = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !open) return;
    const opener = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => {
      dialog.close();
      opener?.focus();
    };
  }, [open]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      // Escape fires "cancel". Let the parent decide (it closes us by setting open=false), and
      // never mid-request.
      onCancel={(event) => {
        event.preventDefault();
        if (!loading) onCancel();
      }}
      onKeyDown={handleKeyDown}
      className={
        "m-auto w-[calc(100%-2rem)] max-w-md rounded-lg border border-border bg-surface p-6 " +
        "text-text shadow-xl backdrop:bg-text/40"
      }
    >
      {open && (
        <div className="flex flex-col gap-4">
          <h2 id={titleId} className="font-display text-lg font-bold text-text">
            {title}
          </h2>
          <div id={bodyId} className="text-body text-text-muted">
            {children}
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          {/* Cancel is first in the DOM, so showModal() focuses it: the safe default for a
              destructive action. Visually, confirm sits on top on phones and on the right on
              desktop. */}
          <div className="flex flex-col-reverse gap-3 sm:flex-row">
            <Button variant="secondary" disabled={loading} onClick={onCancel}>
              {cancelLabel}
            </Button>
            <Button
              variant={destructive ? "danger" : "primary"}
              loading={loading}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  );
}
