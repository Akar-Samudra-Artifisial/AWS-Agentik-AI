import type { CaseCategory, CaseStatus, Channel, OrderStatus, ResolutionType } from "./api-types";

/** Semua waktu ditampilkan di WIB (UTC+7) agar konsisten di rekaman demo, apa pun zona browser. */
export const TIME_ZONE = "Asia/Jakarta";
export const TIME_ZONE_LABEL = "WIB";
export const TIME_ZONE_HINT = "WIB (UTC+7)";

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat("en-US", {
  timeZone: TIME_ZONE,
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const timeOnly = new Intl.DateTimeFormat("en-US", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});
const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

/** Rupiah integer gaya Inggris: `Rp349,000`. */
export function formatIdr(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value < 0 ? "-" : ""}Rp${number.format(Math.abs(value))}`;
}

export function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : number.format(value);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : `${dateTime.format(d)} ${TIME_ZONE_LABEL}`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : `${timeOnly.format(d)} ${TIME_ZONE_LABEL}`;
}

export function formatRelative(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((t - now) / 1000);
  const abs = Math.abs(sec);
  if (abs < 45) return "just now";
  if (abs < 3600) return rtf.format(Math.round(sec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(sec / 3600), "hour");
  return rtf.format(Math.round(sec / 86400), "day");
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "—";
  // Bandingkan nilai SETELAH dibulatkan agar tidak muncul "1000 ms", "60 s", "60 min", "24.0 h".
  if (Math.round(ms) < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 10 && Number(s.toFixed(1)) < 10) return `${s.toFixed(1)} s`;
  if (Math.round(s) < 60) return `${Math.round(s)} s`;
  const m = s / 60;
  if (Math.round(m) < 60) return `${Math.round(m)} min`;
  const h = m / 60;
  if (Number(h.toFixed(1)) < 24) return `${h.toFixed(1)} h`;
  const d = (h / 24).toFixed(1);
  return `${d} ${d === "1.0" ? "day" : "days"}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${formatNumber(n)} ${n === 1 ? one : many}`;
}

export function diffMs(from: string | null | undefined, to: string | null | undefined): number | null {
  if (!from || !to) return null;
  const d = new Date(to).getTime() - new Date(from).getTime();
  return Number.isNaN(d) ? null : d;
}

export const CHANNEL_LABEL: Record<Channel, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
};

export const STATUS_LABEL: Record<CaseStatus, string> = {
  open: "New",
  investigating: "Investigating",
  awaiting_customer: "Awaiting customer",
  awaiting_approval: "Awaiting approval",
  escalated: "Escalated",
  resolved: "Resolved",
  error: "Error",
};

export const CATEGORY_LABEL: Record<CaseCategory, string> = {
  late_delivery: "Late delivery",
  lost_package: "Lost package",
  not_received: "Not received",
  status_inquiry: "Status inquiry",
  address_change: "Address change",
  other: "Other",
};

export const RESOLUTION_LABEL: Record<ResolutionType, string> = {
  auto_resolved: "Auto-resolved",
  approved_by_staff: "Approved by staff",
  rejected_by_staff: "Rejected by staff",
  escalated: "Escalated to human",
};

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  processing: "Processing",
  shipped: "Shipped",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
  refunded: "Refunded",
};

export function labelOf<K extends string>(map: Record<K, string>, key: K | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}
