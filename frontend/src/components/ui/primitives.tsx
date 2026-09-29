import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
      <div>
        <h2 className="text-sm font-bold text-slate-900">{title}</h2>
        {description ? <p className="mt-1 text-xs text-slate-500">{description}</p> : null}
      </div>
      {actions}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-[1.35px] text-slate-400">
          {eyebrow}
        </p>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950">{title}</h1>
        {description ? (
          <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

const badgeTone = {
  slate: "bg-slate-100 text-slate-600 ring-slate-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  purple: "bg-violet-50 text-violet-700 ring-violet-200",
} as const;

export function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: keyof typeof badgeTone;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-1 text-[11px] font-semibold ring-1 ring-inset",
        badgeTone[tone],
      )}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="grid size-12 place-items-center rounded-2xl bg-slate-100 text-slate-500">
        {icon}
      </div>
      <h3 className="mt-4 text-sm font-bold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
