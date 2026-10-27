"use client";

import Link from "next/link";
import { ApprovalCard } from "@/components/ApprovalCard";
import { CaseFeed } from "@/components/CaseTable";
import { type ShareDatum, ShareList, StackedMeter, VolumeChart } from "@/components/charts";
import { IconArrowUpRight, IconShieldCheck } from "@/components/icons";
import { KpiCard } from "@/components/KpiCard";
import { Card, CardHeader, EmptyState, ErrorState, LoadingRows, MoreLink, PageHeader } from "@/components/ui";
import type { CaseCategory, Channel } from "@/lib/api-types";
import { POLL_MS, errorMessage, useApprovals, useCases, useMetrics } from "@/lib/api";
import { CATEGORY_LABEL, CHANNEL_LABEL, formatDuration, formatNumber, plural } from "@/lib/format";
import { bucketByDay } from "@/lib/series";
import { CHANNEL_CHART_COLOR } from "@/lib/tokens";

const CHANNELS: Channel[] = ["whatsapp", "sms", "email"];
const DAYS = 7;

export default function OverviewPage() {
  const metrics = useMetrics();
  const cases = useCases({ limit: 50 });
  const approvals = useApprovals("pending");
  const m = metrics.data;
  const mLoading = !m && !metrics.error;

  // Deret harian dihitung dari daftar kasus (≤50 terbaru) — hanya setelah data ada agar tidak beda dengan render statis.
  const days = cases.data ? bucketByDay(cases.data, DAYS) : null;
  const today = days?.[days.length - 1]?.total ?? 0;
  const weekTotal = days?.reduce((s, d) => s + d.total, 0) ?? 0;

  const byChannel: ShareDatum[] = CHANNELS.map((c) => ({
    key: c,
    label: CHANNEL_LABEL[c],
    value: m?.by_channel?.[c] ?? 0,
    color: CHANNEL_CHART_COLOR[c],
  }));
  const byCategory: ShareDatum[] = Object.entries(m?.by_category ?? {})
    .map(([k, v]) => ({ key: k, label: CATEGORY_LABEL[k as CaseCategory] ?? k, value: v ?? 0 }))
    .sort((a, b) => b.value - a.value);
  const pendingN = m?.totals.pending_approvals ?? approvals.data?.length ?? 0;
  const closed = m ? m.totals.resolved + m.totals.escalated : 0;
  const autoRate = m?.auto_resolution_rate ?? 0;
  const autoCount = Math.round(autoRate * closed);
  const sent = Object.values(m?.messages_sent ?? {}).reduce<number>((s, v) => s + (v ?? 0), 0);

  const statusData: ShareDatum[] = m
    ? [
        { key: "resolved", label: "Resolved", value: m.totals.resolved, tone: "success" },
        { key: "active", label: "Active", value: m.totals.active, tone: "info" },
        { key: "escalated", label: "Escalated", value: m.totals.escalated, tone: "danger" },
        { key: "pending", label: "Awaiting approval", value: pendingN, tone: "warning" },
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Overview"
        description="How the AI agent is performing and what needs a staff decision."
        action={
          <>
            <span className="text-xs text-zinc-500">Auto-refreshes every {POLL_MS / 1000} s</span>
            <Link
              href="/simulator/"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 text-sm font-medium text-white shadow-sm ring-1 ring-accent-700/40 ring-inset hover:bg-accent-700"
            >
              Run a scenario
              <IconArrowUpRight className="size-4" />
            </Link>
          </>
        }
      />

      {metrics.error ? (
        <Card className="mb-6">
          <ErrorState message={errorMessage(metrics.error)} onRetry={() => metrics.mutate()} />
        </Card>
      ) : null}

      <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Total cases"
          value={m ? formatNumber(m.totals.cases) : "—"}
          delta={days ? { text: `+${formatNumber(today)} today`, tone: today > 0 ? "accent" : "neutral" } : undefined}
          spark={days?.map((d) => d.total)}
          sparkLabel={days ? `New cases per day, last ${DAYS} days: ${days.map((d) => d.total).join(", ")}` : undefined}
          hint={m ? `${formatNumber(m.totals.active)} active · ${formatNumber(m.totals.resolved)} resolved` : undefined}
          loading={mLoading}
        />
        <KpiCard
          label="Auto-resolution rate"
          value={m ? `${Math.round(autoRate * 100)}%` : "—"}
          delta={m ? { text: "No staff needed", tone: "success" } : undefined}
          meter={m ? { value: autoRate, label: "Auto-resolution rate" } : undefined}
          hint={m ? `${formatNumber(autoCount)} of ${plural(closed, "closed case")} resolved by the agent alone` : undefined}
          loading={mLoading}
        />
        <KpiCard
          label="First response · p50"
          value={formatDuration(m?.first_response_ms.p50)}
          delta={m?.first_response_ms.p90 != null ? { text: `p90 ${formatDuration(m.first_response_ms.p90)}` } : undefined}
          meter={
            m && m.first_response_ms.p90
              ? { value: m.first_response_ms.p50 / m.first_response_ms.p90, label: "Median first response relative to p90" }
              : undefined
          }
          hint="Inbound message → first agent reply"
          loading={mLoading}
        />
        <KpiCard
          label="Time to resolve · p50"
          value={formatDuration(m?.resolution_ms.p50)}
          delta={m ? { text: `${formatNumber(m.totals.escalated)} escalated`, tone: m.totals.escalated > 0 ? "danger" : "neutral" } : undefined}
          segments={
            m
              ? [
                  { key: "auto", label: "Auto-resolved", value: autoCount, tone: "success" },
                  { key: "staff", label: "Resolved with staff", value: Math.max(0, m.totals.resolved - autoCount), tone: "accent" },
                  { key: "esc", label: "Escalated", value: m.totals.escalated, tone: "danger" },
                ]
              : undefined
          }
          hint="First message → case closed · outcome mix"
          loading={mLoading}
        />
      </section>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-12">
        <Card className="xl:col-span-8">
          <CardHeader
            title="Case volume"
            subtitle={`New cases per day · last ${DAYS} days (WIB)`}
            action={
              days ? (
                <span className="text-right">
                  <span className="block text-xl font-semibold tracking-tight tabular-nums text-zinc-950">{formatNumber(weekTotal)}</span>
                  <span className="block text-[11px] text-zinc-500">this week</span>
                </span>
              ) : null
            }
          />
          {cases.error ? (
            <ErrorState message={errorMessage(cases.error)} onRetry={() => cases.mutate()} />
          ) : (
            <VolumeChart data={days ?? []} loading={!days} />
          )}
        </Card>

        <Card className="xl:col-span-4">
          <CardHeader title="Case status" subtitle={m ? `${plural(m.totals.cases, "case")} in total` : undefined} />
          <div className="px-5 py-5">
            {m ? <StackedMeter data={statusData} label="Case status" /> : <LoadingRows rows={2} label="Loading metrics…" />}
          </div>
          <div className="border-t border-zinc-100 px-5 py-4">
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">Replies sent</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums text-zinc-950">{m ? formatNumber(sent) : "—"}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">Closed</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums text-zinc-950">{m ? formatNumber(closed) : "—"}</dd>
              </div>
            </dl>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-12">
        <Card className="flex flex-col xl:col-span-4" as="section">
          <CardHeader
            id="pending-title"
            icon={<IconShieldCheck />}
            title="Needs your decision"
            subtitle={approvals.data ? plural(approvals.data.length, "pending refund") : "Refunds above the auto-limit"}
            action={<MoreLink href="/approvals/">All</MoreLink>}
          />
          {approvals.error ? (
            <ErrorState message={errorMessage(approvals.error)} onRetry={() => approvals.mutate()} />
          ) : !approvals.data ? (
            <LoadingRows rows={2} label="Loading approvals…" />
          ) : approvals.data.length === 0 ? (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                icon={<IconShieldCheck />}
                title="All clear"
                hint="Refunds above the auto-approval limit will appear here for a decision."
              />
            </div>
          ) : (
            <div className="space-y-3 bg-zinc-50/60 p-3">
              {approvals.data.slice(0, 3).map((a) => (
                <ApprovalCard key={a.approval_id} approval={a} compact onDecided={() => approvals.mutate()} />
              ))}
            </div>
          )}
        </Card>

        <Card className="xl:col-span-8">
          <CardHeader
            id="recent-title"
            title="Recent activity"
            subtitle="Latest cases handled by the agent"
            action={<MoreLink href="/cases/">All cases</MoreLink>}
          />
          {cases.error ? (
            <ErrorState message={errorMessage(cases.error)} onRetry={() => cases.mutate()} />
          ) : !cases.data ? (
            <LoadingRows rows={5} label="Loading cases…" />
          ) : cases.data.length === 0 ? (
            <EmptyState title="No cases yet" hint="Send a message from the Simulator to get started." />
          ) : (
            <CaseFeed cases={cases.data.slice(0, 6)} />
          )}
        </Card>
      </div>

      <section aria-label="Case breakdown" className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Cases by channel" subtitle="Where customers reach out" />
          <ShareList data={byChannel} loading={mLoading} />
        </Card>
        <Card>
          <CardHeader title="Cases by category" subtitle="What customers complain about" />
          <ShareList data={byCategory} loading={mLoading} />
        </Card>
      </section>
    </>
  );
}
