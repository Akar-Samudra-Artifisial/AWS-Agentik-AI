"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { AgentTimeline } from "@/components/AgentTimeline";
import { ApprovalCard } from "@/components/ApprovalCard";
import { ChannelBadge } from "@/components/ChannelBadge";
import { ChatThread } from "@/components/ChatThread";
import { CustomerCard, OrderCard } from "@/components/OrderCard";
import { PriorityBadge, StatusBadge } from "@/components/StatusBadge";
import { Card, CardHeader, EmptyState, ErrorState, Field, LoadingRows, SimulatedTag, Skeleton } from "@/components/ui";
import { ApiError, errorMessage, useCase } from "@/lib/api";
import type { CaseDetail } from "@/lib/api-types";
import {
  CATEGORY_LABEL,
  RESOLUTION_LABEL,
  diffMs,
  formatDateTime,
  formatDuration,
  formatIdr,
  labelOf,
} from "@/lib/format";
import { maskText } from "@/lib/mask";

export default function CasePage() {
  return (
    <Suspense fallback={<LoadingRows rows={6} label="Memuat kasus…" />}>
      <CaseView />
    </Suspense>
  );
}

function CaseView() {
  const id = useSearchParams().get("id");
  const { data, error, mutate } = useCase(id);

  if (!id) {
    return (
      <Card>
        <EmptyState
          title="ID kasus tidak ada"
          hint="Buka kasus dari daftar kasus."
          action={<Link href="/cases/" className="font-medium text-brand-700 hover:underline">Ke daftar kasus</Link>}
        />
      </Card>
    );
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-2 text-sm text-stone-500">
        <Link href="/cases/" className="hover:text-stone-800 hover:underline">Kasus</Link>
        <span aria-hidden="true"> / </span>
        <span className="font-mono text-stone-800">{id}</span>
      </nav>

      {error && !data ? (
        <Card>
          {error instanceof ApiError && error.status === 404 ? (
            <EmptyState title="Kasus tidak ditemukan" hint={`Tidak ada kasus dengan ID ${id}. Jika baru dikirim dari Simulator, tunggu beberapa detik.`} />
          ) : (
            <ErrorState message={errorMessage(error)} onRetry={() => mutate()} />
          )}
        </Card>
      ) : !data ? (
        <DetailSkeleton />
      ) : (
        <CaseDetailView detail={data} />
      )}
    </>
  );
}

function CaseDetailView({ detail }: { detail: CaseDetail }) {
  const c = detail.case;
  const firstResponse = diffMs(c.first_inbound_at, c.first_response_at);
  // Status final tanpa resolved_at (mis. escalated) dihitung sampai update terakhir; "Berjalan" hanya untuk kasus aktif.
  const isFinal = c.status === "resolved" || c.status === "escalated";
  const duration = diffMs(c.first_inbound_at ?? c.created_at, c.resolved_at ?? (isFinal ? c.updated_at : null));
  const pending = detail.approvals.filter((a) => a.status === "pending");
  const history = detail.approvals.filter((a) => a.status !== "pending");
  // case.summary bisa basi (mis. "pending approval") setelah kasus selesai; resolusi lebih akurat.
  const headline = (c.status === "resolved" && c.resolution?.summary) || c.summary;

  return (
    <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-mono text-2xl font-semibold tracking-tight text-stone-900">{c.case_id}</h1>
            <StatusBadge status={c.status} />
            <ChannelBadge channel={c.channel} />
            <PriorityBadge priority={c.priority} />
          </div>
          {headline ? <p className="mt-1.5 max-w-3xl text-[15px] text-stone-600">{maskText(headline)}</p> : null}
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          {pending.map((a) => (
            <ApprovalCard key={a.approval_id} approval={a} />
          ))}
          <div className="grid gap-6 2xl:grid-cols-2">
            <Card>
              <CardHeader title="Percakapan" subtitle={`${detail.messages.length} pesan`} />
              <ChatThread messages={detail.messages} />
            </Card>
            <Card>
              <CardHeader title="Linimasa agen" subtitle="Klik langkah untuk melihat JSON input/output" />
              <AgentTimeline events={detail.events} />
            </Card>
          </div>
        </div>

        <aside className="space-y-4" aria-label="Info kasus">
          <Card>
            <CardHeader title="Kasus" />
            <dl className="divide-y divide-stone-100 px-5 py-2">
              <Field label="Kategori" value={labelOf(CATEGORY_LABEL, c.category)} />
              <Field label="Prioritas" value={<PriorityBadge priority={c.priority} />} />
              <Field label="Respons pertama" value={formatDuration(firstResponse)} />
              <Field label="Durasi" value={duration != null ? formatDuration(duration) : "Berjalan"} />
              <Field label="Dibuat" value={formatDateTime(c.created_at)} />
              <Field label="Diperbarui" value={formatDateTime(c.updated_at)} />
              {c.resolution_type ? <Field label="Resolusi" value={labelOf(RESOLUTION_LABEL, c.resolution_type)} /> : null}
            </dl>
            {c.resolution ? (
              <div className="border-t border-stone-100 px-5 py-3 text-sm">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="font-medium text-stone-800">{c.resolution.action ?? "Resolusi"}</span>
                  <SimulatedTag label="Pembayaran disimulasikan" />
                </div>
                {c.resolution.amount_idr != null ? <p>{formatIdr(c.resolution.amount_idr)}</p> : null}
                {c.resolution.voucher_code ? <p className="font-mono text-xs">Voucher {c.resolution.voucher_code}</p> : null}
                {c.resolution.summary ? <p className="mt-1 text-stone-600">{maskText(c.resolution.summary)}</p> : null}
              </div>
            ) : null}
          </Card>
          <CustomerCard customer={detail.customer} />
          <OrderCard order={detail.order} />
          {history.length ? (
            <section aria-label="Riwayat approval" className="space-y-3">
              <h2 className="text-[15px] font-semibold text-stone-900">Riwayat approval</h2>
              {history.map((a) => (
                <ApprovalCard key={a.approval_id} approval={a} compact />
              ))}
            </section>
          ) : null}
        </aside>
      </div>
    </>
  );
}

function DetailSkeleton() {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">Memuat detail kasus…</span>
      <Skeleton className="h-9 w-80" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  );
}
