"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { caseHref } from "@/components/CaseTable";
import { IconShieldCheck } from "@/components/icons";
import { ApprovalStatusBadge } from "@/components/StatusBadge";
import { Card, CardHeader, EmptyState, ErrorState, LoadingRows, PageHeader, SectionHeading, SimulatedTag } from "@/components/ui";
import type { ApprovalWithCase } from "@/lib/api-types";
import { errorMessage, useApprovals } from "@/lib/api";
import { formatDateTime, formatIdr, formatNumber, formatRelative } from "@/lib/format";
import { maskText } from "@/lib/mask";

export default function ApprovalsPage() {
  const pending = useApprovals("pending");
  // GET /approvals tanpa status = pending (default backend), jadi riwayat diambil per status.
  const approved = useApprovals("approved");
  const rejected = useApprovals("rejected");
  const historyError = approved.error ?? rejected.error;
  const historyLoaded = approved.data != null && rejected.data != null;
  const history = [...(approved.data ?? []), ...(rejected.data ?? [])].sort((a, b) =>
    (b.decided_at ?? b.requested_at).localeCompare(a.decided_at ?? a.requested_at),
  );

  const refreshHistory = () => {
    void approved.mutate();
    void rejected.mutate();
  };
  const refresh = () => {
    void pending.mutate();
    refreshHistory();
  };

  const pendingAmount = (pending.data ?? []).reduce((s, a) => s + (a.amount_idr ?? 0), 0);

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Refunds above the auto-approval limit need a staff decision. The agent can’t pay out without one — it resumes the case as soon as you decide."
      />

      <section aria-label="Approval summary" className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryTile label="Awaiting decision" value={pending.data ? formatNumber(pending.data.length) : "—"} tone={pending.data?.length ? "warning" : undefined} />
        <SummaryTile label="Amount on hold" value={pending.data ? formatIdr(pendingAmount) : "—"} note={<SimulatedTag label="Simulated payment" />} />
        <SummaryTile
          label="Decided"
          value={historyLoaded ? formatNumber(history.length) : "—"}
          note={
            historyLoaded ? (
              <span className="text-xs text-zinc-500">
                {formatNumber(approved.data?.length ?? 0)} approved · {formatNumber(rejected.data?.length ?? 0)} rejected
              </span>
            ) : null
          }
        />
      </section>

      <section aria-labelledby="pending-h">
        <SectionHeading
          id="pending-h"
          title="Awaiting decision"
          count={pending.data?.length}
          description="Review the agent’s reasoning, then approve or reject."
        />
        {pending.error ? (
          <Card>
            <ErrorState message={errorMessage(pending.error)} onRetry={() => pending.mutate()} />
          </Card>
        ) : !pending.data ? (
          <Card>
            <LoadingRows rows={3} label="Loading approvals…" />
          </Card>
        ) : pending.data.length === 0 ? (
          <Card>
            <EmptyState icon={<IconShieldCheck />} title="Queue is empty" hint="No refunds are waiting for approval. New requests appear here within seconds." />
          </Card>
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">
            {pending.data.map((a) => (
              <ApprovalCard key={a.approval_id} approval={a} onDecided={refresh} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="history-h" className="mt-10">
        <Card>
          <CardHeader
            id="history-h"
            title="Decision history"
            subtitle={historyLoaded ? `${formatNumber(history.length)} decided refunds · newest first` : "Approved and rejected refunds"}
          />
          {historyError ? (
            <ErrorState message={errorMessage(historyError)} onRetry={refreshHistory} />
          ) : !historyLoaded ? (
            <LoadingRows rows={3} label="Loading history…" />
          ) : history.length === 0 ? (
            <EmptyState title="No decisions yet" hint="Approved and rejected refunds will be listed here." />
          ) : (
            <HistoryTable rows={history} />
          )}
        </Card>
      </section>
    </>
  );
}

function SummaryTile({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note?: ReactNode;
  tone?: "warning";
}) {
  return (
    <div className="rounded-xl bg-white px-5 py-4 shadow-card ring-1 ring-zinc-950/[0.06]">
      <p className="flex items-center gap-2 text-[13px] font-medium text-zinc-500">
        {tone === "warning" ? <span aria-hidden="true" className="size-1.5 rounded-full bg-warning-500" /> : null}
        {label}
      </p>
      <p className="mt-2 text-[26px] leading-none font-semibold tracking-[-0.03em] tabular-nums text-zinc-950">{value}</p>
      {note ? <div className="mt-2.5">{note}</div> : null}
    </div>
  );
}

function HistoryTable({ rows }: { rows: ApprovalWithCase[] }) {
  const th = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500 first:pl-5 last:pr-5";
  const td = "px-4 py-3.5 align-top first:pl-5 last:pr-5";
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="bg-zinc-50/80 shadow-[inset_0_-1px_0_var(--color-zinc-200)]">
          <tr>
            <th scope="col" className={th}>Approval</th>
            <th scope="col" className={th}>Case</th>
            <th scope="col" className={`${th} text-right`}>Amount</th>
            <th scope="col" className={th}>Decision</th>
            <th scope="col" className={`${th} w-[34%]`}>Reason</th>
            <th scope="col" className={`${th} text-right`}>Decided</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((a) => (
            <tr key={a.approval_id} className="hover:bg-zinc-50/70">
              <td className={`${td} font-mono text-[12.5px] whitespace-nowrap text-zinc-700`}>{a.approval_id}</td>
              <td className={td}>
                <Link href={caseHref(a.case_id)} className="font-mono text-[12.5px] font-medium whitespace-nowrap text-accent-700 hover:underline">
                  {a.case_id}
                </Link>
                {a.case?.customer_name ? <p className="mt-0.5 text-xs text-zinc-500">{a.case.customer_name}</p> : null}
              </td>
              <td className={`${td} text-right font-semibold whitespace-nowrap tabular-nums text-zinc-900`}>{formatIdr(a.amount_idr)}</td>
              <td className={td}>
                <ApprovalStatusBadge status={a.status} />
                {a.decided_by ? <p className="mt-1 text-xs text-zinc-500">by {a.decided_by}</p> : null}
              </td>
              <td className={`${td} max-w-0 text-[13px] text-zinc-600`}>
                <p className="line-clamp-2" title={a.reason ? maskText(a.reason) : undefined}>
                  {a.reason ? maskText(a.reason) : "—"}
                </p>
                {a.note ? <p className="mt-1 truncate text-xs text-zinc-500">Note: {maskText(a.note)}</p> : null}
              </td>
              <td className={`${td} text-right text-[13px] whitespace-nowrap text-zinc-500`}>
                <time dateTime={a.decided_at ?? a.requested_at} title={formatDateTime(a.decided_at ?? a.requested_at)}>
                  {formatRelative(a.decided_at ?? a.requested_at)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
