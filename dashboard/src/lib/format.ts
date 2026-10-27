import type { CaseCategory, CaseStatus, Channel, OrderStatus, ResolutionType } from "./api-types";

const idr = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" });
const timeOnly = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const rtf = new Intl.RelativeTimeFormat("id-ID", { numeric: "auto" });

export function formatIdr(value: number | null | undefined): string {
  return value == null ? "—" : idr.format(value);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateTime.format(d);
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : timeOnly.format(d);
}

export function formatRelative(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((t - now) / 1000);
  const abs = Math.abs(sec);
  if (abs < 45) return "baru saja";
  if (abs < 3600) return rtf.format(Math.round(sec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(sec / 3600), "hour");
  return rtf.format(Math.round(sec / 86400), "day");
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} dtk`;
  const m = s / 60;
  if (m < 60) return `${Math.round(m)} mnt`;
  const h = m / 60;
  if (h < 24) return `${h.toFixed(1)} jam`;
  return `${(h / 24).toFixed(1)} hari`;
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
  open: "Baru",
  investigating: "Diselidiki",
  awaiting_customer: "Menunggu pelanggan",
  awaiting_approval: "Menunggu approval",
  escalated: "Dieskalasi",
  resolved: "Selesai",
  error: "Error",
};

export const CATEGORY_LABEL: Record<CaseCategory, string> = {
  late_delivery: "Terlambat",
  lost_package: "Paket hilang",
  not_received: "Tidak diterima",
  status_inquiry: "Tanya status",
  address_change: "Ubah alamat",
  other: "Lainnya",
};

export const RESOLUTION_LABEL: Record<ResolutionType, string> = {
  auto_resolved: "Otomatis",
  approved_by_staff: "Disetujui staf",
  rejected_by_staff: "Ditolak staf",
  escalated: "Eskalasi",
};

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  processing: "Diproses",
  shipped: "Dikirim",
  in_transit: "Dalam perjalanan",
  out_for_delivery: "Diantar kurir",
  delivered: "Terkirim",
  cancelled: "Dibatalkan",
  refunded: "Direfund",
};

export function labelOf<K extends string>(map: Record<K, string>, key: K | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}
