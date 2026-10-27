import type { ReactNode } from "react";
import { Skeleton, cx } from "./ui";

export function KpiCard({
  label,
  value,
  unit,
  hint,
  tone = "default",
  loading,
}: {
  label: string;
  value: ReactNode;
  /** Satuan kecil di samping angka, mis. "cases". */
  unit?: string;
  hint?: ReactNode;
  tone?: "default" | "accent" | "warning" | "danger";
  loading?: boolean;
}) {
  return (
    <div
      className={cx(
        "relative overflow-hidden rounded-xl border bg-white px-5 py-4 shadow-xs",
        tone === "default" && "border-stone-200",
        tone === "accent" && "border-brand-100",
        tone === "warning" && "border-amber-300",
        tone === "danger" && "border-red-200",
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "absolute inset-x-0 top-0 h-1",
          tone === "default" && "bg-stone-200",
          tone === "accent" && "bg-brand-600",
          tone === "warning" && "bg-amber-400",
          tone === "danger" && "bg-red-500",
        )}
      />
      <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className="mt-1.5 flex items-baseline gap-1.5">
          <span className="text-3xl font-semibold tabular-nums tracking-tight text-stone-900">{value}</span>
          {unit ? <span className="text-sm font-medium text-stone-500">{unit}</span> : null}
        </p>
      )}
      {hint ? <p className="mt-1 text-xs text-stone-500">{hint}</p> : null}
    </div>
  );
}
