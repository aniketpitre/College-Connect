import { useEffect, useRef, useState } from "react";

interface Props {
  open: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  /** Money, marks and record changes require a written reason, which goes into the audit log. */
  requireReason?: boolean;
  danger?: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", requireReason, danger, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      // showModal() gives the backdrop, focus trap and top layer; the attribute is a fallback for test DOMs.
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!open && dialog.open) dialog.close?.();
  }, [open]);

  const canConfirm = !requireReason || reason.trim().length >= 5;

  return (
    <dialog ref={ref} className="confirm-dialog" aria-labelledby="confirm-title" onCancel={onCancel}>
      <h2 id="confirm-title">{title}</h2>
      <div className="confirm-message">{message}</div>
      {requireReason && (
        <label className="confirm-reason">
          Reason (recorded in the audit log)
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} />
        </label>
      )}
      <div className="confirm-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className={danger ? "btn btn-danger" : "btn btn-primary"}
          disabled={!canConfirm}
          onClick={() => {
            onConfirm(reason.trim());
            setReason("");
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
