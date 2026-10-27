import type { ApprovalStatus, CaseStatus, Priority } from "@/lib/api-types";
import { STATUS_LABEL } from "@/lib/format";
import { cx } from "./ui";

/*
 * Satu palet status untuk seluruh dashboard:
 * hijau = selesai/approved, kuning = menunggu, merah = eskalasi/error/rejected, biru = diproses, abu = baru.
 */
const CASE_STYLE: Record<CaseStatus, string> = {
  open: "bg-stone-100 text-stone-700 ring-stone-300",
  investigating: "bg-blue-50 text-blue-800 ring-blue-300",
  awaiting_customer: "bg-amber-50 text-amber-800 ring-amber-300",
  awaiting_approval: "bg-amber-100 text-amber-900 ring-amber-400",
  escalated: "bg-red-50 text-red-800 ring-red-300",
  resolved: "bg-emerald-50 text-emerald-800 ring-emerald-300",
  error: "bg-red-100 text-red-900 ring-red-400",
};

// Ikon teks agar status tidak bergantung pada warna saja.
const CASE_ICON: Record<CaseStatus, string> = {
  open: "○",
  investigating: "◔",
  awaiting_customer: "◷",
  awaiting_approval: "◷",
  escalated: "▲",
  resolved: "✓",
  error: "✕",
};

const BADGE = "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap";

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span className={cx(BADGE, CASE_STYLE[status] ?? CASE_STYLE.open)}>
      <span aria-hidden="true">{CASE_ICON[status] ?? "•"}</span>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

const APPROVAL_STYLE: Record<ApprovalStatus, string> = {
  pending: "bg-amber-100 text-amber-900 ring-amber-400",
  approved: "bg-emerald-50 text-emerald-800 ring-emerald-300",
  rejected: "bg-red-50 text-red-800 ring-red-300",
};

const APPROVAL_ICON: Record<ApprovalStatus, string> = { pending: "◷", approved: "✓", rejected: "✕" };
const APPROVAL_LABEL: Record<ApprovalStatus, string> = { pending: "Pending", approved: "Approved", rejected: "Rejected" };

export function ApprovalStatusBadge({ status }: { status: ApprovalStatus }) {
  return (
    <span className={cx(BADGE, APPROVAL_STYLE[status] ?? APPROVAL_STYLE.pending)}>
      <span aria-hidden="true">{APPROVAL_ICON[status] ?? "•"}</span>
      {APPROVAL_LABEL[status] ?? status}
    </span>
  );
}

/** `short` dipakai di kolom tabel berjudul "Priority" agar tidak redundan. */
export function PriorityBadge({ priority, short = false }: { priority: Priority; short?: boolean }) {
  const suffix = short ? "" : " priority";
  if (priority !== "high") {
    return <span className={cx(BADGE, "bg-white text-stone-600 ring-stone-200")}>Normal{suffix}</span>;
  }
  return (
    <span className={cx(BADGE, "bg-red-600 font-semibold text-white ring-red-600")}>
      <span aria-hidden="true">!</span>High{suffix}
    </span>
  );
}
