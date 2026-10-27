"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardHeader, EmptyState, Skeleton } from "./ui";

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  color: string;
}

export function BarChartCard({
  title,
  data,
  loading,
}: {
  title: string;
  data: BarDatum[];
  loading?: boolean;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const summary = data.map((d) => `${d.label}: ${d.value}`).join(", ");

  return (
    <Card>
      <CardHeader title={title} subtitle={loading ? undefined : `${total} ${total === 1 ? "case" : "cases"} total`} />
      <div className="h-64 px-2 py-4">
        {loading ? (
          <Skeleton className="mx-3 h-full" />
        ) : total === 0 ? (
          <EmptyState title="No data yet" hint="Charts fill in as cases arrive." />
        ) : (
          <figure className="h-full" aria-label={`${title}. ${summary}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                <CartesianGrid vertical={false} stroke="#e7e5e4" />
                <XAxis dataKey="label" tick={{ fontSize: 13, fill: "#57534e" }} tickLine={false} axisLine={false} interval={0} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#78716c" }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "#f5f5f4" }} formatter={(v) => [v, "Cases"]} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                  {data.map((d) => (
                    <Cell key={d.key} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </figure>
        )}
      </div>
    </Card>
  );
}
