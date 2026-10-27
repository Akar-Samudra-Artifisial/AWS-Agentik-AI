import type { ApprovalStatus, CaseStatus, Priority } from "@/lib/api-types";
import { STATUS_LABEL } from "@/lib/format";
import { cx } from "./ui";

// Status: hijau (resolved), kuning (awaiting_*), merah (escalated/error), biru (investigating).
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

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap",
        CASE_STYLE[status] ?? CASE_STYLE.open,
      )}
    >
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

const APPROVAL_LABEL: Record<ApprovalStatus, string> = {
  pending: "◷ Pending",
  approved: "✓ Disetujui",
  rejected: "✕ Ditolak",
};

export function ApprovalStatusBadge({ status }: { status: ApprovalStatus }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        APPROVAL_STYLE[status] ?? APPROVAL_STYLE.pending,
      )}
    >
      {APPROVAL_LABEL[status] ?? status}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  if (priority !== "high") return <span className="text-xs text-stone-500">Normal</span>;
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
      <span aria-hidden="true">!</span>Tinggi
    </span>
  );
}
