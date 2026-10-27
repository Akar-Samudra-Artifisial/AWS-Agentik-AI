import type { CaseSummary, Channel } from "./api-types";
import { TIME_ZONE } from "./format";

const DAY_MS = 86_400_000;
const dayKeyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" });
const dayLabelFmt = new Intl.DateTimeFormat("en-US", { timeZone: TIME_ZONE, month: "short", day: "numeric" });

/** Kunci hari `YYYY-MM-DD` di WIB. */
export function dayKey(iso: string | number | Date): string {
  return dayKeyFmt.format(new Date(iso));
}

export interface DayBucket {
  key: string;
  label: string;
  total: number;
  autoResolved: number;
  closed: number;
  byChannel: Record<Channel, number>;
}

/** Kelompokkan kasus per hari (WIB) untuk `days` hari terakhir, termasuk hari kosong. */
export function bucketByDay(cases: CaseSummary[], days: number, now: number = Date.now()): DayBucket[] {
  const buckets: DayBucket[] = [];
  const index = new Map<string, DayBucket>();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * DAY_MS);
    const b: DayBucket = {
      key: dayKey(d),
      label: dayLabelFmt.format(d),
      total: 0,
      autoResolved: 0,
      closed: 0,
      byChannel: { whatsapp: 0, sms: 0, email: 0 },
    };
    buckets.push(b);
    index.set(b.key, b);
  }
  for (const c of cases) {
    const b = index.get(dayKey(c.created_at));
    if (!b) continue;
    b.total += 1;
    b.byChannel[c.channel] = (b.byChannel[c.channel] ?? 0) + 1;
    if (c.status === "resolved" || c.status === "escalated") b.closed += 1;
    if (c.resolution_type === "auto_resolved") b.autoResolved += 1;
  }
  return buckets;
}
