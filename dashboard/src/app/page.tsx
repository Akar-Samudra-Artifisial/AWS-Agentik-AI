"use client";

import { ApprovalCard } from "@/components/ApprovalCard";
import { BarChartCard, type BarDatum } from "@/components/BarChartCard";
import { CHANNEL_COLOR } from "@/components/ChannelBadge";
import { CaseTable } from "@/components/CaseTable";
import { KpiCard } from "@/components/KpiCard";
import { Card, EmptyState, ErrorState, LoadingRows, MoreLink, PageHeader, SectionHeading } from "@/components/ui";
import type { CaseCategory, Channel } from "@/lib/api-types";
import { POLL_MS, errorMessage, useApprovals, useCases, useMetrics } from "@/lib/api";
import { CATEGORY_LABEL, CHANNEL_LABEL, formatDuration, formatNumber } from "@/lib/format";

const CHANNELS: Channel[] = ["whatsapp", "sms", "email"];
const CATEGORY_COLOR = "#1f6f86";

export default function OverviewPage() {
  const metrics = useMetrics();
  const cases = useCases({ limit: 8 });
  const approvals = useApprovals("pending");
  const m = metrics.data;
  const mLoading = !m && !metrics.error;

  const byChannel: BarDatum[] = CHANNELS.map((c) => ({
    key: c,
    label: CHANNEL_LABEL[c],
    value: m?.by_channel?.[c] ?? 0,
    color: CHANNEL_COLOR[c],
  }));
  const byCategory: BarDatum[] = Object.entries(m?.by_category ?? {}).map(([k, v]) => ({
    key: k,
    label: CATEGORY_LABEL[k as CaseCategory] ?? k,
    value: v ?? 0,
    color: CATEGORY_COLOR,
  }));
  const pendingN = m?.totals.pending_approvals ?? approvals.data?.length ?? 0;
  const closed = m ? m.totals.resolved + m.totals.escalated : 0;

  return (
    <>
      <PageHeader
        title="Overview"
        description={`How the AI agent is performing and what needs a staff decision. Auto-refreshes every ${POLL_MS / 1000} seconds.`}
      />

      {metrics.error ? (
        <Card className="mb-6">
          <ErrorState message={errorMessage(metrics.error)} onRetry={() => metrics.mutate()} />
        </Card>
      ) : null}

      <section aria-label="Key metrics" className="grid grid-cols-2 gap-4 md:grid-cols-3 2xl:grid-cols-6">
        <KpiCard
          label="Total cases"
          value={m ? formatNumber(m.totals.cases) : "—"}
          hint={m ? `${formatNumber(m.totals.active)} active · ${formatNumber(m.totals.resolved)} resolved` : undefined}
          loading={mLoading}
        />
        <KpiCard
          label="Auto-resolution rate"
          value={m ? `${Math.round((m.auto_resolution_rate ?? 0) * 100)}%` : "—"}
          hint={m ? `Resolved without staff, of ${formatNumber(closed)} closed cases` : undefined}
          tone="accent"
          loading={mLoading}
        />
        <KpiCard
          label="First response · p50"
          value={formatDuration(m?.first_response_ms.p50)}
          hint={m?.first_response_ms.p90 != null ? `p90 ${formatDuration(m.first_response_ms.p90)} · inbound → first reply` : undefined}
          loading={mLoading}
        />
        <KpiCard
          label="Time to resolve · p50"
          value={formatDuration(m?.resolution_ms.p50)}
          hint="First message → case closed"
          loading={mLoading}
        />
        <KpiCard
          label="Escalated"
          value={m ? formatNumber(m.totals.escalated) : "—"}
          unit={m ? (m.totals.escalated === 1 ? "case" : "cases") : undefined}
          hint="Handed off to a human agent"
          tone={m && m.totals.escalated > 0 ? "danger" : "default"}
          loading={mLoading}
        />
        <KpiCard
          label="Pending approvals"
          value={m ? formatNumber(pendingN) : "—"}
          hint="Refunds above the auto-approval limit"
          tone={pendingN > 0 ? "warning" : "default"}
          loading={mLoading}
        />
      </section>

      <div className="mt-8 grid gap-6 xl:grid-cols-3">
        <section aria-labelledby="pending-title" className="min-w-0">
          <SectionHeading
            id="pending-title"
            title="Needs your decision"
            count={approvals.data?.length}
            action={<MoreLink href="/approvals/">All approvals</MoreLink>}
          />
          {approvals.error ? (
            <Card>
              <ErrorState message={errorMessage(approvals.error)} onRetry={() => approvals.mutate()} />
            </Card>
          ) : !approvals.data ? (
            <Card>
              <LoadingRows rows={2} label="Loading approvals…" />
            </Card>
          ) : approvals.data.length === 0 ? (
            <Card>
              <EmptyState title="All clear" hint="Refunds above the auto-approval limit will appear here." />
            </Card>
          ) : (
            <div className="space-y-3">
              {approvals.data.slice(0, 3).map((a) => (
                <ApprovalCard key={a.approval_id} approval={a} compact onDecided={() => approvals.mutate()} />
              ))}
            </div>
          )}
        </section>

        <section aria-labelledby="recent-title" className="min-w-0 xl:col-span-2">
          <SectionHeading id="recent-title" title="Recent activity" action={<MoreLink href="/cases/">All cases</MoreLink>} />
          <Card>
            {cases.error ? (
              <ErrorState message={errorMessage(cases.error)} onRetry={() => cases.mutate()} />
            ) : !cases.data ? (
              <LoadingRows rows={5} label="Loading cases…" />
            ) : cases.data.length === 0 ? (
              <EmptyState title="No cases yet" hint="Send a message from the Simulator to get started." />
            ) : (
              <CaseTable cases={cases.data.slice(0, 8)} dense />
            )}
          </Card>
        </section>
      </div>

      <section aria-label="Case breakdown" className="mt-8 grid gap-6 md:grid-cols-2">
        <BarChartCard title="Cases by channel" data={byChannel} loading={mLoading} />
        <BarChartCard title="Cases by category" data={byCategory} loading={mLoading} />
      </section>
    </>
  );
}
