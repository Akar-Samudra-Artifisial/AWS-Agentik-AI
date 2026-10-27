import type { Customer, Order } from "@/lib/api-types";
import { CHANNEL_LABEL, ORDER_STATUS_LABEL, formatDateTime, formatIdr, labelOf } from "@/lib/format";
import { maskEmail, maskPhone } from "@/lib/mask";
import { Card, CardHeader, Field, SimulatedTag } from "./ui";

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
        <CardHeader title="Pesanan" />
        <p className="px-5 py-4 text-sm text-stone-500">Kasus belum terhubung ke pesanan.</p>
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
      <CardHeader title="Pesanan" action={<SimulatedTag label="kurir simulated" />} />
      <dl className="divide-y divide-stone-100 px-5 py-2">
        <Field label="ID" value={<span className="font-mono">{order.order_id}</span>} />
        <Field label="Status" value={labelOf(ORDER_STATUS_LABEL, order.status)} />
        <Field label="Nilai" value={formatIdr(order.total_idr)} />
        <Field label="ETA" value={formatDateTime(order.eta)} />
        <Field
          label="Keterlambatan"
          value={
            late == null ? (
              <span className="text-stone-500">—</span>
            ) : late > 0 ? (
              <span className="rounded bg-red-50 px-1.5 text-red-800">
                {late} hari{order.status === "refunded" ? " (saat refund)" : ""}
              </span>
            ) : (
              <span className="text-stone-600">Tepat waktu</span>
            )
          }
        />
        {sinceScan != null ? <Field label="Scan terakhir" value={`${sinceScan} hari lalu`} /> : null}
        {order.last_scan_location ? <Field label="Lokasi terakhir" value={order.last_scan_location} /> : null}
        {order.courier ? <Field label="Kurir" value={order.courier} /> : null}
        {order.redelivery_at ? <Field label="Kirim ulang" value={formatDateTime(order.redelivery_at)} /> : null}
        {order.refund ? (
          <Field
            label="Refund"
            value={
              <span className="inline-flex items-center gap-1.5">
                {formatIdr(order.refund.amount_idr)} · {order.refund.status}
                <SimulatedTag />
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
      <CardHeader title="Pelanggan" />
      {customer ? (
        <dl className="divide-y divide-stone-100 px-5 py-2">
          <Field label="Nama" value={customer.name} />
          <Field label="ID" value={<span className="font-mono">{customer.customer_id}</span>} />
          <Field label="Telepon" value={<span className="font-mono">{maskPhone(customer.phone_e164)}</span>} />
          <Field label="Email" value={<span className="font-mono">{maskEmail(customer.email)}</span>} />
          {customer.preferred_channel ? (
            <Field label="Kanal favorit" value={CHANNEL_LABEL[customer.preferred_channel]} />
          ) : null}
        </dl>
      ) : (
        <p className="px-5 py-4 text-sm text-stone-500">Data pelanggan tidak tersedia.</p>
      )}
    </Card>
  );
}
