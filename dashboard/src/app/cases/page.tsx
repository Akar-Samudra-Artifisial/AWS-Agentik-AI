"use client";

import { useId, useState } from "react";
import { CaseTable } from "@/components/CaseTable";
import { Card, EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/ui";
import type { CaseStatus, Channel } from "@/lib/api-types";
import { errorMessage, useCases } from "@/lib/api";
import { CHANNEL_LABEL, STATUS_LABEL } from "@/lib/format";

const STATUSES = Object.keys(STATUS_LABEL) as CaseStatus[];
const CHANNELS = Object.keys(CHANNEL_LABEL) as Channel[];

const selectClass =
  "rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus:border-brand-600";

export default function CasesPage() {
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [channel, setChannel] = useState<Channel | "">("");
  const [query, setQuery] = useState("");
  const ids = { status: useId(), channel: useId(), q: useId() };
  const { data, error, mutate } = useCases({ status, channel, limit: 50 });

  const q = query.trim().toLowerCase();
  const rows = (data ?? []).filter(
    (c) => !q || c.case_id.toLowerCase().includes(q) || (c.customer_name ?? "").toLowerCase().includes(q) || (c.order_id ?? "").toLowerCase().includes(q),
  );
  const filtered = Boolean(status || channel || q);

  return (
    <>
      <PageHeader title="Kasus" description="Semua kasus, terbaru di atas. Klik baris untuk melihat percakapan dan langkah agen." />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.q} className="text-xs font-medium text-stone-600">Cari</label>
          <input
            id={ids.q}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ID kasus, pesanan, atau nama"
            className={`${selectClass} w-64`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.status} className="text-xs font-medium text-stone-600">Status</label>
          <select id={ids.status} value={status} onChange={(e) => setStatus(e.target.value as CaseStatus | "")} className={selectClass}>
            <option value="">Semua status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABEL[s]}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.channel} className="text-xs font-medium text-stone-600">Kanal</label>
          <select id={ids.channel} value={channel} onChange={(e) => setChannel(e.target.value as Channel | "")} className={selectClass}>
            <option value="">Semua kanal</option>
            {CHANNELS.map((c) => (
              <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>
            ))}
          </select>
        </div>
        {filtered ? (
          <button
            type="button"
            onClick={() => {
              setStatus("");
              setChannel("");
              setQuery("");
            }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-stone-600 hover:bg-stone-100"
          >
            Reset filter
          </button>
        ) : null}
        {data ? <p className="ml-auto text-sm text-stone-500" aria-live="polite">{rows.length} kasus</p> : null}
      </div>

      <Card>
        {error ? (
          <ErrorState message={errorMessage(error)} onRetry={() => mutate()} />
        ) : !data ? (
          <LoadingRows rows={8} label="Memuat kasus…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title={filtered ? "Tidak ada kasus yang cocok" : "Belum ada kasus"}
            hint={filtered ? "Ubah atau reset filter." : "Kirim pesan dari Simulator untuk membuat kasus pertama."}
          />
        ) : (
          <CaseTable cases={rows} />
        )}
      </Card>
    </>
  );
}
