import { useState } from "react";

import { ApiError } from "../../lib/api";
import { Modal } from "./Modal";
import { Button } from "./button";

export function DeleteConfirmationModal({
  title,
  description,
  confirmLabel = "确认删除",
  onClose,
  onConfirm,
}: {
  title: string;
  description: string;
  confirmLabel?: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setDeleting(true);
    setError(null);
    try {
      await onConfirm();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "删除失败，请稍后重试。");
      setDeleting(false);
    }
  }

  return (
    <Modal title={title} description="这是永久删除操作，无法撤销。" onClose={onClose}>
      <div className="space-y-4 p-5">
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-800">
          {description}
        </p>
        {error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" onClick={onClose} disabled={deleting}>取消</Button>
          <Button variant="danger" onClick={confirm} disabled={deleting}>
            {deleting ? "正在删除…" : confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
