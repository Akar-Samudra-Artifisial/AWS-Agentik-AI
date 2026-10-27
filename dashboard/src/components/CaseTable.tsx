"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CaseSummary } from "@/lib/api-types";
import { CATEGORY_LABEL, RESOLUTION_LABEL, formatDateTime, formatRelative, labelOf } from "@/lib/format";
import { maskText } from "@/lib/mask";
import { ChannelBadge } from "./ChannelBadge";
import { IconChevronRight } from "./icons";
import { PriorityBadge, StatusBadge } from "./StatusBadge";
import { Avatar } from "./ui";

export function caseHref(id: string): string {
  return `/case/?id=${encodeURIComponent(id)}`;
}

/** Sama dengan halaman detail: summary bisa basi setelah kasus selesai; resolusi lebih akurat. */
function headlineOf(c: CaseSummary): string {
  return (c.status === "resolved" && c.resolution_summary) || c.summary || "";
}

function Updated({ iso }: { iso: string }) {
  return (
    <time dateTime={iso} title={formatDateTime(iso)} className="tabular-nums">
      {formatRelative(iso)}
    </time>
  );
}

export function CaseTable({ cases }: { cases: CaseSummary[] }) {
  const router = useRouter();
  const th = "bg-zinc-50 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500 first:pl-5 last:pr-5 shadow-[inset_0_-1px_0_var(--color-zinc-200)]";
  const td = "px-4 py-3.5 first:pl-5 last:pr-5";

  return (
    // Tabel memanjang mengikuti halaman (scroll halaman); hanya scroll horizontal di layar sempit.
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead>
          <tr>
            <th scope="col" className={th}>Case</th>
            <th scope="col" className={th}>Customer</th>
            <th scope="col" className={th}>Status</th>
            <th scope="col" className={th}>Channel</th>
            <th scope="col" className={th}>Category</th>
            <th scope="col" className={th}>Priority</th>
            <th scope="col" className={`${th} w-[30%]`}>Summary</th>
            <th scope="col" className={`${th} text-right`}>Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {cases.map((c) => {
            const headline = headlineOf(c);
            return (
              <tr
                key={c.case_id}
                onClick={() => router.push(caseHref(c.case_id))}
                className="group cursor-pointer align-middle transition-colors hover:bg-zinc-50"
              >
                <td className={td}>
                  <Link
                    href={caseHref(c.case_id)}
                    onClick={(e) => e.stopPropagation()}
                    className="font-mono text-[12.5px] font-medium whitespace-nowrap text-zinc-900 underline-offset-2 group-hover:text-accent-700 hover:underline"
                  >
                    {c.case_id}
                  </Link>
                  <p className="mt-0.5 font-mono text-[11.5px] text-zinc-400">{c.order_id ?? "No order"}</p>
                </td>
                <td className={td}>
                  <span className="flex items-center gap-2.5">
                    <Avatar name={c.customer_name} size="sm" />
                    <span className="whitespace-nowrap text-zinc-800">{c.customer_name ?? "—"}</span>
                  </span>
                </td>
                <td className={td}>
                  <StatusBadge status={c.status} />
                  {c.resolution_type ? (
                    <p className="mt-1 text-[11.5px] whitespace-nowrap text-zinc-500">{labelOf(RESOLUTION_LABEL, c.resolution_type)}</p>
                  ) : null}
                </td>
                <td className={td}>
                  <ChannelBadge channel={c.channel} />
                </td>
                <td className={`${td} whitespace-nowrap text-zinc-600`}>{labelOf(CATEGORY_LABEL, c.category)}</td>
                <td className={td}>
                  <PriorityBadge priority={c.priority} short />
                </td>
                <td className={`${td} max-w-0 text-zinc-500`}>
                  <p className="truncate" title={headline ? maskText(headline) : undefined}>
                    {headline ? maskText(headline) : "—"}
                  </p>
                </td>
                <td className={`${td} whitespace-nowrap text-right text-[13px] text-zinc-500`}>
                  <span className="inline-flex items-center gap-1.5">
                    <Updated iso={c.updated_at} />
                    <IconChevronRight className="size-4 text-zinc-300 transition-colors group-hover:text-zinc-500" />
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Daftar aktivitas ringkas (Overview): satu baris per kasus, seluruh baris adalah tautan. */
export function CaseFeed({ cases }: { cases: CaseSummary[] }) {
  return (
    <ul className="divide-y divide-zinc-100">
      {cases.map((c) => {
        const headline = headlineOf(c);
        return (
          <li key={c.case_id}>
            <Link
              href={caseHref(c.case_id)}
              className="group flex items-center gap-3.5 px-5 py-3 transition-colors hover:bg-zinc-50 focus-visible:-outline-offset-2"
            >
              <Avatar name={c.customer_name} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-zinc-900">{c.customer_name ?? "Unknown customer"}</span>
                  <span className="font-mono text-[11.5px] whitespace-nowrap text-zinc-400">{c.case_id}</span>
                </span>
                <span className="mt-0.5 block truncate text-[13px] text-zinc-500" title={headline ? maskText(headline) : undefined}>
                  {headline ? maskText(headline) : labelOf(CATEGORY_LABEL, c.category)}
                </span>
              </span>
              <span className="hidden shrink-0 sm:block">
                <ChannelBadge channel={c.channel} size="sm" />
              </span>
              <span className="shrink-0">
                <StatusBadge status={c.status} />
              </span>
              <span className="hidden w-20 shrink-0 text-right text-xs text-zinc-500 md:block">
                <Updated iso={c.updated_at} />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
