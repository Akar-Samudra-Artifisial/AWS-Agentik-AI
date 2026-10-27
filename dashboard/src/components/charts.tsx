"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Channel } from "@/lib/api-types";
import { CHANNEL_LABEL, formatNumber } from "@/lib/format";
import type { DayBucket } from "@/lib/series";
import { CHANNEL_CHART_COLOR, TOKENS } from "@/lib/tokens";
import { TONE_DOT, type Tone } from "./StatusBadge";
import { Skeleton, cx } from "./ui";

const CHANNELS: Channel[] = ["whatsapp", "sms", "email"];

function ChannelLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
      {CHANNELS.map((c) => (
        <li key={c} className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2 rounded-sm" style={{ backgroundColor: CHANNEL_CHART_COLOR[c] }} />
          {CHANNEL_LABEL[c]}
        </li>
      ))}
    </ul>
  );
}

/** Volume kasus harian, ditumpuk per kanal (gradasi aksen). */
export function VolumeChart({ data, loading }: { data: DayBucket[]; loading?: boolean }) {
  if (loading) return <Skeleton className="m-5 h-56" />;
  const rows = data.map((d) => ({ label: d.label, ...d.byChannel, total: d.total }));
  const summary = data.map((d) => `${d.label}: ${d.total}`).join(", ");
  return (
    <div className="px-3 pt-4 pb-3">
      <div className="mb-3 px-2">
        <ChannelLegend />
      </div>
      <figure className="h-56" aria-label={`New cases per day. ${summary}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -20 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke={TOKENS.zinc100} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: TOKENS.zinc500 }} tickLine={false} axisLine={false} interval={0} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: TOKENS.zinc400 }} tickLine={false} axisLine={false} width={40} />
            <Tooltip
              cursor={{ fill: TOKENS.zinc100, opacity: 0.6 }}
              contentStyle={{
                borderRadius: 10,
                border: `1px solid ${TOKENS.zinc200}`,
                boxShadow: "0 8px 24px -8px rgb(24 24 27 / 0.12)",
                fontSize: 12,
                padding: "8px 10px",
              }}
              labelStyle={{ color: TOKENS.zinc900, fontWeight: 600, marginBottom: 4 }}
              formatter={(v, name) => [v, CHANNEL_LABEL[name as Channel] ?? name]}
            />
            {CHANNELS.map((c, i) => (
              <Bar
                key={c}
                dataKey={c}
                stackId="ch"
                fill={CHANNEL_CHART_COLOR[c]}
                radius={i === CHANNELS.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                maxBarSize={36}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </figure>
    </div>
  );
}

export interface ShareDatum {
  key: string;
  label: string;
  value: number;
  /** Nada semantik (status) atau warna hex eksplisit (kanal). */
  tone?: Tone;
  color?: string;
}

/** Daftar batang horizontal dengan nilai + persentase; tanpa SVG agar tajam dan mudah dibaca. */
export function ShareList({ data, loading }: { data: ShareDatum[]; loading?: boolean }) {
  if (loading) {
    return (
      <div className="space-y-4 px-5 py-5">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-6" />
        ))}
      </div>
    );
  }
  const total = data.reduce((s, d) => s + d.value, 0);
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-3.5 px-5 py-5">
      {data.map((d) => {
        const pct = total ? Math.round((d.value / total) * 100) : 0;
        return (
          <li key={d.key}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
              <span className="font-medium text-zinc-700">{d.label}</span>
              <span className="tabular-nums text-zinc-500">
                <span className="font-semibold text-zinc-900">{formatNumber(d.value)}</span>
                <span className="ml-1.5 inline-block w-9 text-right text-xs">{pct}%</span>
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-zinc-100" aria-hidden="true">
              <div
                className={cx("h-full rounded-full", d.tone ? TONE_DOT[d.tone] : !d.color && "bg-accent-500")}
                style={{ width: `${(d.value / max) * 100}%`, ...(d.color ? { backgroundColor: d.color } : {}) }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Satu batang bertumpuk + legenda untuk komposisi status. */
export function StackedMeter({ data, label }: { data: ShareDatum[]; label: string }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-zinc-100" role="img" aria-label={`${label}: ${data.map((d) => `${d.label} ${d.value}`).join(", ")}`}>
        {total > 0
          ? data
              .filter((d) => d.value > 0)
              .map((d) => (
                <span key={d.key} className={cx("h-full", d.tone ? TONE_DOT[d.tone] : "bg-accent-500")} style={{ width: `${(d.value / total) * 100}%` }} />
              ))
          : null}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
        {data.map((d) => (
          <div key={d.key} className="flex items-center justify-between gap-2 text-[13px]">
            <dt className="flex items-center gap-2 text-zinc-600">
              <span aria-hidden="true" className={cx("size-2 rounded-full", d.tone ? TONE_DOT[d.tone] : "bg-accent-500")} />
              {d.label}
            </dt>
            <dd className="font-semibold tabular-nums text-zinc-900">{formatNumber(d.value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
