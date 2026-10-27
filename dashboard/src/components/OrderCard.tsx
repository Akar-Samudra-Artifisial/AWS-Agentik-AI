import type { Customer, Order } from "@/lib/api-types";
import { CHANNEL_LABEL, ORDER_STATUS_LABEL, formatDateTime, formatIdr, labelOf } from "@/lib/format";
import { maskEmail, maskPhone } from "@/lib/mask";
import type { OrderStatus } from "@/lib/api-types";
import { IconPackage, IconUser } from "./icons";
import { Badge, type Tone } from "./StatusBadge";
import { Card, CardHeader, Field, SimulatedTag } from "./ui";

const ORDER_TONE: Record<OrderStatus, Tone> = {
  processing: "neutral",
  shipped: "info",
  in_transit: "info",
  out_for_delivery: "info",
  delivered: "success",
  cancelled: "neutral",
  refunded: "accent",
};

const DAY_MS = 86_400_000;

/** Jumlah hari penuh sejak `iso` (0 bila belum lewat), null bila tidak ada/tidak valid. */
function daysSince(iso: string | null | undefined, now: number = Date.now()): number | null {
  const t = iso ? Date.parse(iso) : NaN;
  return Number.isNaN(t) ? null : Math.max(0, Math.floor((now - t) / DAY_MS));
}

/** Titik akhir (ms) untuk menghitung keterlambatan terhadap eta; null bila tak relevan. */
function lateEnd(order: Order): number | null {
  const at = (iso: string | null | undefined) => {
    const t = iso ? Date.parse(iso) : NaN;
    return Number.isNaN(t) ? null : t;
  };
  switch (order.status) {
    case "delivered":
      return at(order.last_scan_at);
    case "refunded":
      return at(order.refund?.at) ?? at(order.last_scan_at);
    case "cancelled":
      return null;
    default:
      return Date.now();
  }
}

export function OrderCard({ order }: { order: Order | null | undefined }) {
  if (!order) {
    return (
      <Card>
        <CardHeader icon={<IconPackage />} title="Order" />
        <p className="px-5 py-4 text-[13px] text-zinc-500">This case isn’t linked to an order yet.</p>
      </Card>
    );
  }
  // Backend tidak mengirim days_late/days_since_last_scan; dihitung dari eta/last_scan_at.
  // Keterlambatan = eta → titik akhir: sekarang (masih jalan), scan terakhir (terkirim),
  // waktu refund (direfund). Dibatalkan tanpa titik akhir → "—".
  const end = lateEnd(order);
  const late = end != null ? daysSince(order.eta, end) : null;
  const sinceScan = daysSince(order.last_scan_at);
  return (
    <Card>
      <CardHeader icon={<IconPackage />} title="Order" subtitle={order.courier ?? undefined} action={<SimulatedTag label="Simulated courier" />} />
      <dl className="divide-y divide-zinc-100 px-5 py-1">
        <Field label="ID" value={<span className="font-mono text-[12.5px]">{order.order_id}</span>} />
        <Field label="Status" value={<Badge tone={ORDER_TONE[order.status] ?? "neutral"}>{labelOf(ORDER_STATUS_LABEL, order.status)}</Badge>} />
        <Field label="Order value" value={<span className="tabular-nums">{formatIdr(order.total_idr)}</span>} />
        <Field label="ETA" value={formatDateTime(order.eta)} />
        <Field
          label="Delay"
          value={
            late == null ? (
              <span className="text-zinc-400">—</span>
            ) : late > 0 ? (
              <span className="rounded-md bg-danger-50 px-1.5 py-px text-danger-800 ring-1 ring-danger-200 ring-inset">
                {late} {late === 1 ? "day" : "days"} late{order.status === "refunded" ? " (at refund)" : ""}
              </span>
            ) : (
              <span className="text-success-700">On time</span>
            )
          }
        />
        {sinceScan != null ? <Field label="Last scan" value={sinceScan === 0 ? "Today" : `${sinceScan} ${sinceScan === 1 ? "day" : "days"} ago`} /> : null}
        {order.last_scan_location ? <Field label="Last location" value={order.last_scan_location} /> : null}
        {order.courier ? <Field label="Courier" value={order.courier} /> : null}
        {order.redelivery_at ? <Field label="Redelivery" value={formatDateTime(order.redelivery_at)} /> : null}
        {order.refund ? (
          <Field
            label="Refund"
            value={
              <span className="inline-flex flex-col items-end gap-1">
                <span className="whitespace-nowrap">
                  {formatIdr(order.refund.amount_idr)} · <span className="capitalize">{order.refund.status}</span>
                </span>
                <SimulatedTag label="Simulated payment" />
              </span>
            }
          />
        ) : null}
      </dl>
    </Card>
  );
}

export function CustomerCard({ customer }: { customer: Customer | null | undefined }) {
  return (
    <Card>
      <CardHeader icon={<IconUser />} title="Customer" subtitle="Contact details masked" />
      {customer ? (
        <dl className="divide-y divide-zinc-100 px-5 py-1">
          <Field label="Name" value={customer.name} />
          <Field label="ID" value={<span className="font-mono text-[12.5px]">{customer.customer_id}</span>} />
          <Field label="Phone" value={<span className="font-mono text-[12.5px]">{maskPhone(customer.phone_e164)}</span>} />
          <Field label="Email" value={<span className="font-mono text-[12.5px]">{maskEmail(customer.email)}</span>} />
          {customer.preferred_channel ? (
            <Field label="Preferred channel" value={CHANNEL_LABEL[customer.preferred_channel]} />
          ) : null}
        </dl>
      ) : (
        <p className="px-5 py-4 text-[13px] text-zinc-500">Customer details unavailable.</p>
      )}
    </Card>
  );
}
