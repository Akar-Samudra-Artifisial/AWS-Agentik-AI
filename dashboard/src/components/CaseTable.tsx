"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CaseSummary } from "@/lib/api-types";
import { CATEGORY_LABEL, RESOLUTION_LABEL, formatDateTime, formatRelative, labelOf } from "@/lib/format";
import { maskText } from "@/lib/mask";
import { ChannelBadge } from "./ChannelBadge";
import { PriorityBadge, StatusBadge } from "./StatusBadge";

export function caseHref(id: string): string {
  return `/case/?id=${encodeURIComponent(id)}`;
}

export function CaseTable({ cases, dense = false }: { cases: CaseSummary[]; dense?: boolean }) {
  const router = useRouter();
  const cell = dense ? "px-4 py-2.5" : "px-4 py-3";

  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-left text-sm ${dense ? "min-w-[680px]" : "min-w-[900px]"}`}>
        <thead className="border-b border-stone-200 bg-stone-50 text-xs font-semibold uppercase tracking-wide text-stone-500">
          <tr>
            <th scope="col" className={cell}>Case</th>
            <th scope="col" className={cell}>Customer</th>
            <th scope="col" className={cell}>Category</th>
            <th scope="col" className={cell}>Channel</th>
            <th scope="col" className={cell}>Status</th>
            {!dense ? <th scope="col" className={cell}>Priority</th> : null}
            {!dense ? <th scope="col" className={cell}>Summary</th> : null}
            <th scope="col" className={`${cell} text-right`}>Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {cases.map((c) => {
            // Sama dengan halaman detail: summary bisa basi setelah kasus selesai.
            const headline = (c.status === "resolved" && c.resolution_summary) || c.summary;
            return (
              <tr
                key={c.case_id}
                onClick={() => router.push(caseHref(c.case_id))}
                className="cursor-pointer align-top transition-colors hover:bg-brand-50/60"
              >
                <td className={cell}>
                  <Link
                    href={caseHref(c.case_id)}
                    onClick={(e) => e.stopPropagation()}
                    className="font-mono text-[13px] font-medium whitespace-nowrap text-brand-700 underline-offset-2 hover:underline"
                  >
                    {c.case_id}
                  </Link>
                  {c.order_id ? <p className="font-mono text-xs text-stone-500">{c.order_id}</p> : null}
                </td>
                <td className={`${cell} text-stone-800`}>{c.customer_name ?? "—"}</td>
                <td className={`${cell} text-stone-700`}>{labelOf(CATEGORY_LABEL, c.category)}</td>
                <td className={cell}>
                  <ChannelBadge channel={c.channel} />
                </td>
                <td className={cell}>
                  <StatusBadge status={c.status} />
                  {c.resolution_type ? (
                    <p className="mt-1 text-xs text-stone-500">{labelOf(RESOLUTION_LABEL, c.resolution_type)}</p>
                  ) : null}
                </td>
                {!dense ? (
                  <td className={cell}>
                    <PriorityBadge priority={c.priority} short />
                  </td>
                ) : null}
                {!dense ? (
                  <td className={`${cell} max-w-sm text-stone-600`}>
                    <p className="line-clamp-2">{headline ? maskText(headline) : "—"}</p>
                  </td>
                ) : null}
                <td className={`${cell} whitespace-nowrap text-right text-stone-500`}>
                  <time dateTime={c.updated_at} title={formatDateTime(c.updated_at)}>
                    {formatRelative(c.updated_at)}
                  </time>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
