"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { AgentTimeline } from "@/components/AgentTimeline";
import { ApprovalCard } from "@/components/ApprovalCard";
import { ChannelBadge } from "@/components/ChannelBadge";
import { ChatThread } from "@/components/ChatThread";
import { IconBolt, IconChat, IconCheck, IconChevronRight } from "@/components/icons";
import { CustomerCard, OrderCard } from "@/components/OrderCard";
import { Badge, PriorityBadge, StatusBadge } from "@/components/StatusBadge";
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
          action={<Link href="/cases/" className="text-sm font-medium text-accent-700 hover:underline">Go to cases</Link>}
        />
      </Card>
    );
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-[13px] text-zinc-500">
        <Link href="/cases/" className="rounded hover:text-zinc-900">Cases</Link>
        <IconChevronRight className="size-3.5 text-zinc-300" />
        <span className="font-mono text-zinc-900" aria-current="page">{id}</span>
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
      <header className="mb-6 border-b border-zinc-200/70 pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={c.status} />
          <ChannelBadge channel={c.channel} />
          <PriorityBadge priority={c.priority} />
          <Badge tone="neutral" dot={false}>{labelOf(CATEGORY_LABEL, c.category)}</Badge>
        </div>
        <h1 className="mt-3 font-mono text-[26px] leading-tight font-semibold tracking-[-0.02em] text-zinc-950">{c.case_id}</h1>
        {headline ? <p className="mt-2 max-w-3xl text-[15px] leading-relaxed text-zinc-600">{maskText(headline)}</p> : null}
        <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:flex lg:flex-wrap lg:gap-x-10">
          <Stat label="Customer" value={detail.customer?.name ?? "—"} />
          <Stat label="Opened" value={<span title={formatDateTime(c.created_at)}>{formatRelative(c.created_at)}</span>} />
          <Stat label="First response" value={<span className="tabular-nums">{formatDuration(firstResponse)}</span>} />
          <Stat
            label={isFinal ? "Time to close" : "Duration"}
            value={duration != null ? <span className="tabular-nums">{formatDuration(duration)}</span> : <span className="text-info-700">In progress</span>}
          />
          <Stat
            label="Resolution"
            value={c.resolution_type ? labelOf(RESOLUTION_LABEL, c.resolution_type) : <span className="text-zinc-500">Pending</span>}
          />
          <Stat label="Agent steps" value={<span className="tabular-nums">{plural(toolCalls, "tool call")}</span>} />
        </dl>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="min-w-0 space-y-6 xl:col-span-8">
          {pending.map((a) => (
            <ApprovalCard key={a.approval_id} approval={a} onDecided={() => void mutate()} />
          ))}
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

        <aside className="min-w-0 space-y-6 xl:col-span-4" aria-label="Case details">
          {c.resolution ? (
            <Card>
              <CardHeader
                icon={<IconCheck />}
                title="Resolution"
                action={c.resolution.amount_idr != null ? <SimulatedTag label="Simulated payment" /> : null}
              />
              <div className="px-5 py-4 text-sm">
                <p className="font-mono text-[12px] text-zinc-500">{c.resolution.action || "resolution"}</p>
                {c.resolution.amount_idr != null ? (
                  <p className="mt-1 text-[26px] leading-tight font-semibold tracking-[-0.02em] tabular-nums text-zinc-950">
                    {formatIdr(c.resolution.amount_idr)}
                  </p>
                ) : null}
                {c.resolution.voucher_code ? (
                  <p className="mt-2 inline-flex rounded-md bg-accent-50 px-2 py-0.5 font-mono text-xs text-accent-800 ring-1 ring-accent-200 ring-inset">
                    Voucher {c.resolution.voucher_code}
                  </p>
                ) : null}
                {c.resolution.summary ? <p className="mt-2 leading-relaxed text-zinc-600">{maskText(c.resolution.summary)}</p> : null}
              </div>
            </Card>
          ) : null}
          <CustomerCard customer={detail.customer} />
          <OrderCard order={detail.order} />
          <Card>
            <CardHeader title="Case details" />
            <dl className="divide-y divide-zinc-100 px-5 py-1">
              <Field label="Channel" value={<ChannelBadge channel={c.channel} />} />
              <Field label="Priority" value={<PriorityBadge priority={c.priority} short />} />
              <Field label="Created" value={formatDateTime(c.created_at)} />
              <Field label="Updated" value={formatDateTime(c.updated_at)} />
              {c.resolved_at ? <Field label="Closed" value={formatDateTime(c.resolved_at)} /> : null}
            </dl>
          </Card>
          {history.length ? (
            <section aria-labelledby="approval-history-h" className="space-y-3">
              <h2 id="approval-history-h" className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">Approval history</h2>
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
    <div role="status" className="space-y-6">
      <span className="sr-only">Loading case details…</span>
      <div className="space-y-3 border-b border-zinc-200/70 pb-6">
        <Skeleton className="h-5 w-64" />
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-4 w-full max-w-2xl" />
      </div>
      <div className="grid gap-6 xl:grid-cols-12">
        <Skeleton className="h-96 xl:col-span-8" />
        <Skeleton className="h-96 xl:col-span-4" />
      </div>
    </div>
  );
}
