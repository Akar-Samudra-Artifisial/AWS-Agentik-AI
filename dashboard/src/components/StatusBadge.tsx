import type { ReactNode } from "react";
import type { ApprovalStatus, CaseStatus, Priority } from "@/lib/api-types";
import { STATUS_LABEL } from "@/lib/format";
import { IconAlert } from "./icons";
import { cx } from "./ui";

/*
 * Satu palet status untuk seluruh dashboard (token semantik di globals.css):
 * success = selesai/approved, warning = menunggu, danger = eskalasi/error/rejected, info = diproses, netral = baru.
 * Label teks selalu ada sehingga status tidak bergantung pada warna saja.
 */
export type Tone = "neutral" | "info" | "warning" | "danger" | "success" | "accent";

export const TONE_BADGE: Record<Tone, string> = {
  neutral: "bg-zinc-50 text-zinc-700 ring-zinc-950/10",
  info: "bg-info-50 text-info-800 ring-info-200",
  warning: "bg-warning-50 text-warning-800 ring-warning-200",
  danger: "bg-danger-50 text-danger-800 ring-danger-200",
  success: "bg-success-50 text-success-800 ring-success-200",
  accent: "bg-accent-50 text-accent-800 ring-accent-200",
};

export const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-zinc-400",
  info: "bg-info-500",
  warning: "bg-warning-500",
  danger: "bg-danger-500",
  success: "bg-success-500",
  accent: "bg-accent-500",
};

export const CASE_TONE: Record<CaseStatus, Tone> = {
  open: "neutral",
  investigating: "info",
  awaiting_customer: "warning",
  awaiting_approval: "warning",
  escalated: "danger",
  resolved: "success",
  error: "danger",
};

const BADGE =
  "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap";

export function Badge({ tone = "neutral", children, dot = true }: { tone?: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={cx(BADGE, TONE_BADGE[tone])}>
      {dot ? <span aria-hidden="true" className={cx("size-1.5 rounded-full", TONE_DOT[tone])} /> : null}
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <Badge tone={CASE_TONE[status] ?? "neutral"}>{STATUS_LABEL[status] ?? status}</Badge>;
}

const APPROVAL_TONE: Record<ApprovalStatus, Tone> = { pending: "warning", approved: "success", rejected: "danger" };
const APPROVAL_LABEL: Record<ApprovalStatus, string> = { pending: "Pending", approved: "Approved", rejected: "Rejected" };

export function ApprovalStatusBadge({ status }: { status: ApprovalStatus }) {
  return <Badge tone={APPROVAL_TONE[status] ?? "warning"}>{APPROVAL_LABEL[status] ?? status}</Badge>;
}

/** `short` dipakai di kolom tabel berjudul "Priority" agar tidak redundan. */
export function PriorityBadge({ priority, short = false }: { priority: Priority; short?: boolean }) {
  const suffix = short ? "" : " priority";
  if (priority !== "high") {
    return <span className="text-xs font-medium whitespace-nowrap text-zinc-500">Normal{suffix}</span>;
  }
  return (
    <span className={cx(BADGE, "bg-danger-600 font-semibold text-white ring-danger-700")}>
      <IconAlert className="size-3" />
      High{suffix}
    </span>
  );
}
