"use client";

import Link from "next/link";
import { ApprovalCard } from "@/components/ApprovalCard";
import { BarChartCard, type BarDatum } from "@/components/BarChartCard";
import { CHANNEL_COLOR } from "@/components/ChannelBadge";
import { CaseTable } from "@/components/CaseTable";
import { KpiCard } from "@/components/KpiCard";
import { Card, CardHeader, EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/ui";
import type { CaseCategory, Channel } from "@/lib/api-types";
import { errorMessage, useApprovals, useCases, useMetrics } from "@/lib/api";
import { CATEGORY_LABEL, CHANNEL_LABEL, formatDuration } from "@/lib/format";

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

  return (
    <>
      <PageHeader title="Overview" description="Ringkasan kinerja agen dan antrean yang butuh keputusan staf. Data diperbarui tiap 3 detik." />

      {metrics.error ? <ErrorState message={errorMessage(metrics.error)} onRetry={() => metrics.mutate()} /> : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Total kasus" value={m?.totals.cases ?? "—"} loading={mLoading} />
        <KpiCard
          label="Auto-resolved"
          value={m ? `${Math.round((m.auto_resolution_rate ?? 0) * 100)}%` : "—"}
          hint="dari kasus selesai/eskalasi"
          tone="accent"
          loading={mLoading}
        />
        <KpiCard
          label="Respons pertama (p50)"
          value={formatDuration(m?.first_response_ms.p50)}
          hint={m?.first_response_ms.p90 != null ? `p90 ${formatDuration(m.first_response_ms.p90)}` : undefined}
          loading={mLoading}
        />
        <KpiCard label="Eskalasi" value={m?.totals.escalated ?? "—"} loading={mLoading} />
        <KpiCard label="Approval pending" value={m ? pendingN : "—"} tone={pendingN > 0 ? "warning" : "default"} loading={mLoading} />
        <KpiCard label="Kasus aktif" value={m?.totals.active ?? "—"} loading={mLoading} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <section aria-labelledby="pending-title" className="xl:order-last">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="pending-title" className="text-[15px] font-semibold text-stone-900">
              Approval pending
            </h2>
            <Link href="/approvals/" className="text-sm font-medium text-brand-700 hover:underline">
              Semua →
            </Link>
          </div>
          {approvals.error ? (
            <Card>
              <ErrorState message={errorMessage(approvals.error)} />
            </Card>
          ) : !approvals.data ? (
            <Card>
              <LoadingRows rows={2} />
            </Card>
          ) : approvals.data.length === 0 ? (
            <Card>
              <EmptyState title="Tidak ada approval pending" hint="Refund di atas batas akan muncul di sini." />
            </Card>
          ) : (
            <div className="space-y-3">
              {approvals.data.slice(0, 3).map((a) => (
                <ApprovalCard key={a.approval_id} approval={a} compact onDecided={() => approvals.mutate()} />
              ))}
            </div>
          )}
        </section>
        <div className="grid gap-6 md:grid-cols-2 xl:col-span-2">
          <BarChartCard title="Kasus per kanal" data={byChannel} loading={mLoading} />
          <BarChartCard title="Kasus per kategori" data={byCategory} loading={mLoading} />
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Kasus terbaru"
          action={
            <Link href="/cases/" className="text-sm font-medium text-brand-700 hover:underline">
              Lihat semua →
            </Link>
          }
        />
        {cases.error ? (
          <ErrorState message={errorMessage(cases.error)} onRetry={() => cases.mutate()} />
        ) : !cases.data ? (
          <LoadingRows rows={5} />
        ) : cases.data.length === 0 ? (
          <EmptyState title="Belum ada kasus" hint="Kirim pesan dari Simulator untuk memulai." />
        ) : (
          <CaseTable cases={cases.data.slice(0, 8)} dense />
        )}
      </Card>
    </>
  );
}
