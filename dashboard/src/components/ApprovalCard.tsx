"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { Approval, ApprovalWithCase } from "@/lib/api-types";
import { ApiError, STAFF_NAME, decideApproval, errorMessage } from "@/lib/api";
import { formatDateTime, formatIdr, formatRelative } from "@/lib/format";
import { maskText } from "@/lib/mask";
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
        text: `Keputusan diterima (202) — status ${res?.status ?? (pending === "approve" ? "approved" : "rejected")}. Agen sedang melanjutkan kasus.`,
      });
      setPending(null);
      setNote("");
      onDecided?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setResult({ kind: "conflict", text: "Approval ini sudah diputuskan sebelumnya (409). Data diperbarui." });
        setPending(null);
        onDecided?.();
      } else {
        setResult({ kind: "error", text: errorMessage(err) });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <article
      className={cx(
        "rounded-xl border bg-white shadow-sm",
        isPending ? "border-amber-300 ring-1 ring-amber-200" : "border-stone-200",
      )}
      aria-label={`Approval ${approval.approval_id}`}
    >
      <div className={cx("flex flex-wrap items-start justify-between gap-3", compact ? "px-4 pt-3" : "px-5 pt-4")}>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
            Refund · <span className="font-mono normal-case">{approval.approval_id}</span>
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-stone-900">{formatIdr(approval.amount_idr)}</p>
          <p className="mt-0.5 text-sm text-stone-600">
            <Link href={`/case/?id=${encodeURIComponent(approval.case_id)}`} className="font-mono text-brand-700 underline-offset-2 hover:underline">
              {approval.case_id}
            </Link>
            {approval.order_id ? <span className="font-mono"> · {approval.order_id}</span> : null}
            {customer ? <span> · {customer}</span> : null}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <ApprovalStatusBadge status={approval.status} />
          <SimulatedTag label="Pembayaran disimulasikan" />
        </div>
      </div>

      <div className={cx("space-y-2 text-sm", compact ? "px-4 py-2" : "px-5 py-3")}>
        {approval.reason ? (
          <p>
            <span className="font-medium text-stone-700">Alasan: </span>
            <span className="text-stone-800">{maskText(approval.reason)}</span>
          </p>
        ) : null}
        {summary && !compact ? (
          <p className="text-stone-600">
            <span className="font-medium text-stone-700">Ringkasan: </span>
            {maskText(summary)}
          </p>
        ) : null}
        <p className="text-xs text-stone-500">
          Diminta {formatRelative(approval.requested_at)} ({formatDateTime(approval.requested_at)})
          {approval.decided_at
            ? ` · Diputuskan ${formatRelative(approval.decided_at)}${approval.decided_by ? ` oleh ${approval.decided_by}` : ""}`
            : ""}
        </p>
        {approval.note ? <p className="text-xs text-stone-600">Catatan: {approval.note}</p> : null}
      </div>

      {isPending ? (
        <div className={cx("border-t border-stone-100", compact ? "px-4 py-3" : "px-5 py-3.5")}>
          {pending ? (
            <div className="space-y-2.5">
              <label htmlFor={noteId} className="block text-sm font-medium text-stone-700">
                Catatan (opsional)
              </label>
              <textarea
                id={noteId}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-brand-600"
                placeholder="Mis. sudah dicek dengan kurir"
              />
              <p className="text-sm text-stone-700">
                {pending === "approve"
                  ? `Setujui refund ${formatIdr(approval.amount_idr)}? Agen akan mengeksekusi refund (simulasi) dan mengabari pelanggan.`
                  : "Tolak refund? Agen akan meminta maaf dan mengeskalasi ke staf."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={pending === "approve" ? "primary" : "danger"}
                  loading={submitting}
                  onClick={submit}
                >
                  {pending === "approve" ? "Ya, approve" : "Ya, reject"}
                </Button>
                <Button variant="ghost" disabled={submitting} onClick={() => setPending(null)}>
                  Batal
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => setPending("approve")} aria-label={`Approve ${approval.approval_id}`}>
                ✓ Approve
              </Button>
              <Button variant="danger" onClick={() => setPending("reject")} aria-label={`Reject ${approval.approval_id}`}>
                ✕ Reject
              </Button>
            </div>
          )}
        </div>
      ) : null}

      {result ? (
        <p
          role="status"
          className={cx(
            "border-t px-5 py-2.5 text-sm",
            result.kind === "ok" && "border-emerald-100 bg-emerald-50 text-emerald-900",
            result.kind === "conflict" && "border-amber-100 bg-amber-50 text-amber-900",
            result.kind === "error" && "border-red-100 bg-red-50 text-red-800",
          )}
        >
          {result.text}
        </p>
      ) : null}
    </article>
  );
}
