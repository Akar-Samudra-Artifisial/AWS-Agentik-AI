import type { ReactNode } from "react";
import { Skeleton, cx } from "./ui";

export function KpiCard({
  label,
  value,
  hint,
  tone = "default",
  loading,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "accent" | "warning";
  loading?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border bg-white px-5 py-4 shadow-sm",
        tone === "accent" && "border-brand-100 bg-brand-50",
        tone === "warning" && "border-amber-300 bg-amber-50",
        tone === "default" && "border-stone-200",
      )}
    >
      <p className="text-[13px] font-medium text-stone-600">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-stone-900">{value}</p>
      )}
      {hint ? <p className="mt-1 text-xs text-stone-500">{hint}</p> : null}
    </div>
  );
}
