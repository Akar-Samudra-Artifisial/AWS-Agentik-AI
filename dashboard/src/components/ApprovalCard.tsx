"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { Approval, ApprovalWithCase } from "@/lib/api-types";
import { ApiError, STAFF_NAME, decideApproval, errorMessage } from "@/lib/api";
import { formatDateTime, formatIdr, formatRelative } from "@/lib/format";
import { maskText } from "@/lib/mask";
import { IconCheck, IconX } from "./icons";
import { ApprovalStatusBadge } from "./StatusBadge";
import { Button, SimulatedTag, cx } from "./ui";

type Decision = "approve" | "reject";
type Result = { kind: "ok" | "conflict" | "error"; text: string };

export function ApprovalCard({
  approval,
  onDecided,
  compact = false,
}: {
  approval: Approval | ApprovalWithCase;
  onDecided?: () => void;
  compact?: boolean;
}) {
  const [pending, setPending] = useState<Decision | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const noteId = useId();

  const isPending = approval.status === "pending";
  // Ringkasan kasus hanya disertakan oleh GET /approvals (`case`); approval dari detail kasus tidak memuatnya.
  const caseInfo = "case" in approval ? approval.case : null;
  const customer = caseInfo?.customer_name ?? null;
  const summary = caseInfo?.summary || null;

  async function submit() {
    if (!pending) return;
    setSubmitting(true);
    setResult(null);
    try {
      const res = await decideApproval(approval.approval_id, {
        decision: pending,
        decided_by: STAFF_NAME,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      setResult({
        kind: "ok",
        text: `Decision recorded (202) — status: ${res?.status ?? (pending === "approve" ? "approved" : "rejected")}. The agent is resuming the case.`,
      });
      setPending(null);
      setNote("");
      onDecided?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setResult({ kind: "conflict", text: "This approval was already decided (409). Data refreshed." });
        setPending(null);
        onDecided?.();
      } else {
        setResult({ kind: "error", text: errorMessage(err) });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const pad = compact ? "px-4" : "px-5";

  return (
    <article
      className={cx(
        "overflow-hidden rounded-xl bg-white shadow-card ring-1",
        isPending ? "ring-warning-300" : "ring-zinc-950/[0.06]",
      )}
      aria-label={`Approval ${approval.approval_id}`}
    >
      {isPending ? <div aria-hidden="true" className="h-1 bg-warning-500" /> : null}
      <div className={cx(pad, compact ? "pt-3.5" : "pt-5")}>
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">
            Refund request · <span className="font-mono tracking-normal normal-case">{approval.approval_id}</span>
          </p>
          <ApprovalStatusBadge status={approval.status} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <p
            className={cx(
              "leading-none font-semibold tracking-[-0.03em] tabular-nums text-zinc-950",
              compact ? "text-[22px]" : "text-[34px]",
            )}
          >
            {formatIdr(approval.amount_idr)}
          </p>
          <SimulatedTag label="Simulated payment" />
        </div>
      </div>

      <dl className={cx("mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]", pad, compact && "mt-3")}>
        <div className="min-w-0">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">Case</dt>
          <dd className="mt-0.5 truncate">
            <Link
              href={`/case/?id=${encodeURIComponent(approval.case_id)}`}
              className="font-mono text-[12.5px] font-medium whitespace-nowrap text-accent-700 underline-offset-2 hover:underline"
            >
              {approval.case_id}
            </Link>
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">{customer ? "Customer" : "Order"}</dt>
          <dd className="mt-0.5 truncate text-zinc-800">
            {customer ?? <span className="font-mono text-[12.5px]">{approval.order_id ?? "—"}</span>}
            {customer && approval.order_id ? (
              <span className="ml-1.5 font-mono text-[11.5px] text-zinc-400">{approval.order_id}</span>
            ) : null}
          </dd>
        </div>
      </dl>

      <div className={cx("space-y-2.5 text-[13px]", pad, compact ? "py-3" : "py-4")}>
        {approval.reason ? (
          <div className="rounded-lg bg-zinc-50 px-3 py-2.5 ring-1 ring-zinc-950/[0.04] ring-inset">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">Agent’s reason</p>
            <p className={cx("mt-1 leading-relaxed text-zinc-800", compact && "line-clamp-2")}>{maskText(approval.reason)}</p>
          </div>
        ) : null}
        {summary && !compact ? (
          <p className="leading-relaxed text-zinc-600">
            <span className="font-medium text-zinc-800">Case summary: </span>
            {maskText(summary)}
          </p>
        ) : null}
        <p className="text-xs text-zinc-500">
          <span title={formatDateTime(approval.requested_at)}>Requested {formatRelative(approval.requested_at)}</span>
          {approval.decided_at ? (
            <span title={formatDateTime(approval.decided_at)}>
              {` · Decided ${formatRelative(approval.decided_at)}${approval.decided_by ? ` by ${approval.decided_by}` : ""}`}
            </span>
          ) : null}
        </p>
        {approval.note ? <p className="text-xs text-zinc-600">Note: {maskText(approval.note)}</p> : null}
      </div>

      {isPending ? (
        <div className={cx("border-t border-zinc-100 bg-zinc-50/70", pad, compact ? "py-3" : "py-4")}>
          {pending ? (
            <div className="space-y-3">
              <label htmlFor={noteId} className="block text-[13px] font-medium text-zinc-700">
                Note (optional)
              </label>
              <textarea
                id={noteId}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full rounded-lg bg-white px-3 py-2 text-sm shadow-xs ring-1 ring-zinc-950/10 ring-inset placeholder:text-zinc-400 focus:ring-2 focus:ring-accent-500 focus:outline-none"
                placeholder="e.g. Verified with the courier"
              />
              <p className="text-[13px] text-zinc-700">
                {pending === "approve"
                  ? `Approve a ${formatIdr(approval.amount_idr)} refund? The agent will execute the (simulated) refund and notify the customer.`
                  : "Reject this refund? The agent will apologise to the customer and escalate to staff."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={pending === "approve" ? "primary" : "danger"}
                  loading={submitting}
                  onClick={submit}
                >
                  {pending === "approve" ? "Yes, approve" : "Yes, reject"}
                </Button>
                <Button variant="ghost" disabled={submitting} onClick={() => setPending(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" onClick={() => setPending("approve")} aria-label={`Approve refund ${approval.approval_id}`}>
                <IconCheck />
                Approve
              </Button>
              <Button variant="danger" onClick={() => setPending("reject")} aria-label={`Reject refund ${approval.approval_id}`}>
                <IconX />
                Reject
              </Button>
              {!compact ? <span className="ml-auto text-xs text-zinc-500">The agent resumes as soon as you decide.</span> : null}
            </div>
          )}
        </div>
      ) : null}

      {result ? (
        <p
          role="status"
          className={cx(
            "border-t text-[13px]",
            pad,
            "py-2.5",
            result.kind === "ok" && "border-success-100 bg-success-50 text-success-800",
            result.kind === "conflict" && "border-warning-100 bg-warning-50 text-warning-800",
            result.kind === "error" && "border-danger-100 bg-danger-50 text-danger-800",
          )}
        >
          {result.text}
        </p>
      ) : null}
    </article>
  );
}
