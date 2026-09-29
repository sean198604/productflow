import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Modal({
  title,
  description,
  children,
  onClose,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/40 p-4 backdrop-blur-[2px]">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="my-auto w-full max-w-xl rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-bold text-slate-950">{title}</h2>
            {description ? <p className="mt-1 text-xs text-slate-500">{description}</p> : null}
          </div>
          <button
            type="button"
            aria-label="关闭"
            onClick={onClose}
            className="grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
          >
            <X className="size-4" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
