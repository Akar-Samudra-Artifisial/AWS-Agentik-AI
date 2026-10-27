"use client";

import type { ReactNode } from "react";
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { TOKENS } from "@/lib/tokens";
import { TONE_DOT, type Tone } from "./StatusBadge";
import { SURFACE, Skeleton, cx } from "./ui";

const DELTA_TONE: Record<Tone, string> = {
  neutral: "bg-zinc-100 text-zinc-600",
  info: "bg-info-50 text-info-700",
  warning: "bg-warning-50 text-warning-700",
  danger: "bg-danger-50 text-danger-700",
  success: "bg-success-50 text-success-700",
  accent: "bg-accent-50 text-accent-700",
};

export function KpiCard({
  label,
  value,
  unit,
  hint,
  delta,
  spark,
  sparkLabel,
  meter,
  segments,
  loading,
}: {
  label: string;
  value: ReactNode;
  /** Satuan kecil di samping angka, mis. "cases". */
  unit?: string;
  hint?: ReactNode;
  /** Chip konteks kecil di kanan atas (mis. "+3 today"). */
  delta?: { text: string; tone?: Tone };
  /** Deret nilai untuk sparkline (urut waktu). */
  spark?: number[];
  sparkLabel?: string;
  /** Meter 0..1 bila tidak ada deret waktu. */
  meter?: { value: number; label: string };
  /** Komposisi (mis. resolved vs escalated) sebagai batang bertumpuk tipis. */
  segments?: Array<{ key: string; label: string; value: number; tone: Tone }>;
  loading?: boolean;
}) {
  const sparkData = spark?.map((v, i) => ({ i, v }));
  return (
    <div className={cx(SURFACE, "flex min-h-[148px] flex-col px-5 pt-4 pb-4")}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-medium text-zinc-500">{label}</p>
        {delta && !loading ? (
          <span className={cx("rounded-full px-2 py-px text-[11px] font-semibold whitespace-nowrap tabular-nums", DELTA_TONE[delta.tone ?? "neutral"])}>
            {delta.text}
          </span>
        ) : null}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-24" />
      ) : (
        <p className="mt-2 flex items-baseline gap-1.5">
          <span className="text-[30px] leading-none font-semibold tracking-[-0.03em] tabular-nums text-zinc-950">{value}</span>
          {unit ? <span className="text-sm font-medium text-zinc-400">{unit}</span> : null}
        </p>
      )}
      <div className="mt-auto pt-3">
        {sparkData && sparkData.length > 1 && !loading ? (
          <figure className="-mx-1 h-10" aria-label={sparkLabel}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                <defs>
                  <linearGradient id={`spark-${label.replace(/\W+/g, "")}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={TOKENS.accent500} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={TOKENS.accent500} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis hide domain={[0, "dataMax"]} />
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={TOKENS.accent600}
                  strokeWidth={1.75}
                  fill={`url(#spark-${label.replace(/\W+/g, "")})`}
                  isAnimationActive={false}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </figure>
        ) : meter && !loading ? (
          <div>
            <div
              className="h-1.5 overflow-hidden rounded-full bg-zinc-100"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(meter.value * 100)}
              aria-label={meter.label}
            >
              <div className="h-full rounded-full bg-accent-500" style={{ width: `${Math.max(0, Math.min(1, meter.value)) * 100}%` }} />
            </div>
          </div>
        ) : segments && !loading ? (
          <div
            className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-zinc-100"
            role="img"
            aria-label={segments.map((g) => `${g.label} ${g.value}`).join(", ")}
          >
            {segments
              .filter((g) => g.value > 0)
              .map((g) => (
                <span key={g.key} className={cx("h-full", TONE_DOT[g.tone])} style={{ flexGrow: g.value }} />
              ))}
          </div>
        ) : null}
        {hint ? <p className={cx("text-xs text-zinc-500", (sparkData || meter || segments) && "mt-2")}>{hint}</p> : null}
      </div>
    </div>
  );
}
