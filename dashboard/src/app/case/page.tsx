"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { AgentTimeline } from "@/components/AgentTimeline";
import { ApprovalCard } from "@/components/ApprovalCard";
import { ChannelBadge } from "@/components/ChannelBadge";
import { ChatThread } from "@/components/ChatThread";
import { IconBolt, IconChat } from "@/components/icons";
import { CustomerCard, OrderCard } from "@/components/OrderCard";
import { PriorityBadge, StatusBadge } from "@/components/StatusBadge";
import { Card, CardHeader, EmptyState, ErrorState, Field, LoadingRows, SimulatedTag, Skeleton, Stat } from "@/components/ui";
import { ApiError, errorMessage, useCase } from "@/lib/api";
import type { CaseDetail } from "@/lib/api-types";
import {
  CATEGORY_LABEL,
  RESOLUTION_LABEL,
  diffMs,
  formatDateTime,
  formatDuration,
  formatIdr,
  formatRelative,
  labelOf,
  plural,
} from "@/lib/format";
import { maskText } from "@/lib/mask";

export default function CasePage() {
  return (
    <Suspense fallback={<LoadingRows rows={6} label="Loading case…" />}>
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
          title="No case ID provided"
          hint="Open a case from the case list."
          action={<Link href="/cases/" className="font-medium text-brand-700 hover:underline">Go to cases</Link>}
        />
      </Card>
    );
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-stone-500">
        <Link href="/cases/" className="hover:text-stone-800 hover:underline">Cases</Link>
        <span aria-hidden="true"> / </span>
        <span className="font-mono text-stone-800" aria-current="page">{id}</span>
      </nav>

      {error && !data ? (
        <Card>
          {error instanceof ApiError && error.status === 404 ? (
            <EmptyState
              title="Case not found"
              hint={`There is no case with ID ${id}. If it was just sent from the Simulator, wait a few seconds.`}
            />
          ) : (
            <ErrorState message={errorMessage(error)} onRetry={() => mutate()} />
          )}
        </Card>
      ) : !data ? (
        <DetailSkeleton />
      ) : (
        <CaseDetailView detail={data} mutate={mutate} />
      )}
    </>
  );
}

function CaseDetailView({ detail, mutate }: { detail: CaseDetail; mutate: () => Promise<unknown> }) {
  const c = detail.case;
  const firstResponse = diffMs(c.first_inbound_at, c.first_response_at);
  // Status final tanpa resolved_at (mis. escalated) dihitung sampai update terakhir; "In progress" hanya untuk kasus aktif.
  const isFinal = c.status === "resolved" || c.status === "escalated";
  const duration = diffMs(c.first_inbound_at ?? c.created_at, c.resolved_at ?? (isFinal ? c.updated_at : null));
  const pending = detail.approvals.filter((a) => a.status === "pending");
  const history = detail.approvals.filter((a) => a.status !== "pending");
  // case.summary bisa basi (mis. "pending approval") setelah kasus selesai; resolusi lebih akurat.
  const headline = (c.status === "resolved" && c.resolution?.summary) || c.summary;
  const toolCalls = detail.events.filter((e) => e.type === "tool_call").length;

  return (
    <>
      <Card as="div" className="mb-6">
        <header className="px-5 pt-5 pb-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-mono text-2xl font-semibold tracking-tight text-stone-900">{c.case_id}</h1>
            <StatusBadge status={c.status} />
            <ChannelBadge channel={c.channel} />
            <PriorityBadge priority={c.priority} />
          </div>
          {headline ? <p className="mt-2 max-w-4xl text-[15px] leading-relaxed text-stone-700">{maskText(headline)}</p> : null}
        </header>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 border-t border-stone-100 bg-stone-50/60 px-5 py-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Category" value={labelOf(CATEGORY_LABEL, c.category)} />
          <Stat label="Customer" value={detail.customer?.name ?? "—"} />
          <Stat label="Opened" value={<span title={formatDateTime(c.created_at)}>{formatRelative(c.created_at)}</span>} />
          <Stat label="First response" value={formatDuration(firstResponse)} />
          <Stat
            label={isFinal ? "Time to close" : "Duration"}
            value={duration != null ? formatDuration(duration) : <span className="text-blue-700">In progress</span>}
          />
          <Stat
            label="Resolution"
            value={c.resolution_type ? labelOf(RESOLUTION_LABEL, c.resolution_type) : <span className="text-stone-500">Pending</span>}
          />
        </dl>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-6">
          {pending.map((a) => (
            <ApprovalCard key={a.approval_id} approval={a} onDecided={() => void mutate()} />
          ))}
          <div className="grid gap-6 2xl:grid-cols-2">
            <Card>
              <CardHeader
                icon={<IconChat />}
                title="Conversation"
                subtitle={`${plural(detail.messages.length, "message")} · contact details masked`}
              />
              <ChatThread messages={detail.messages} />
            </Card>
            <Card>
              <CardHeader
                icon={<IconBolt />}
                title="Agent timeline"
                subtitle={`${plural(toolCalls, "tool call")} · select a step to inspect its JSON`}
              />
              <AgentTimeline events={detail.events} />
            </Card>
          </div>
        </div>

        <aside className="min-w-0 space-y-4" aria-label="Case details">
          <Card>
            <CardHeader title="Case details" />
            <dl className="divide-y divide-stone-100 px-5 py-2">
              <Field label="Channel" value={<ChannelBadge channel={c.channel} />} />
              <Field label="Priority" value={<PriorityBadge priority={c.priority} short />} />
              <Field label="Created" value={formatDateTime(c.created_at)} />
              <Field label="Updated" value={formatDateTime(c.updated_at)} />
              {c.resolved_at ? <Field label="Closed" value={formatDateTime(c.resolved_at)} /> : null}
            </dl>
            {c.resolution ? (
              <div className="border-t border-stone-100 px-5 py-3.5 text-sm">
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-[13px] font-medium text-stone-800">{c.resolution.action || "Resolution"}</span>
                  {c.resolution.amount_idr != null ? <SimulatedTag label="Simulated payment" /> : null}
                </div>
                {c.resolution.amount_idr != null ? (
                  <p className="text-lg font-semibold tabular-nums text-stone-900">{formatIdr(c.resolution.amount_idr)}</p>
                ) : null}
                {c.resolution.voucher_code ? <p className="font-mono text-xs">Voucher {c.resolution.voucher_code}</p> : null}
                {c.resolution.summary ? <p className="mt-1 text-stone-600">{maskText(c.resolution.summary)}</p> : null}
              </div>
            ) : null}
          </Card>
          <CustomerCard customer={detail.customer} />
          <OrderCard order={detail.order} />
          {history.length ? (
            <section aria-labelledby="approval-history-h" className="space-y-3">
              <h2 id="approval-history-h" className="text-base font-semibold text-stone-900">Approval history</h2>
              {history.map((a) => (
                <ApprovalCard key={a.approval_id} approval={a} compact onDecided={() => void mutate()} />
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
      <span className="sr-only">Loading case details…</span>
      <Skeleton className="h-32 w-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  );
}
