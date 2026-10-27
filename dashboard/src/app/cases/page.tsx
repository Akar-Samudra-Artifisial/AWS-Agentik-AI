"use client";

import { useId, useState } from "react";
import { CaseTable } from "@/components/CaseTable";
import { Button, Card, EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/ui";
import type { CaseStatus, Channel } from "@/lib/api-types";
import { errorMessage, useCases } from "@/lib/api";
import { CHANNEL_LABEL, STATUS_LABEL, plural } from "@/lib/format";

const STATUSES = Object.keys(STATUS_LABEL) as CaseStatus[];
const CHANNELS = Object.keys(CHANNEL_LABEL) as Channel[];

const controlClass =
  "rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-xs focus:border-brand-600";

export default function CasesPage() {
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [channel, setChannel] = useState<Channel | "">("");
  const [query, setQuery] = useState("");
  const ids = { status: useId(), channel: useId(), q: useId() };
  const { data, error, mutate } = useCases({ status, channel, limit: 50 });

  const q = query.trim().toLowerCase();
  const rows = (data ?? []).filter(
    (c) =>
      !q ||
      c.case_id.toLowerCase().includes(q) ||
      (c.customer_name ?? "").toLowerCase().includes(q) ||
      (c.order_id ?? "").toLowerCase().includes(q),
  );
  const filtered = Boolean(status || channel || q);

  return (
    <>
      <PageHeader
        title="Cases"
        description="Every customer complaint the agent has handled, newest first. Select a row to see the conversation and the agent’s steps."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.q} className="text-xs font-medium text-stone-600">Search</label>
          <input
            id={ids.q}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Case ID, order ID or customer name"
            className={`${controlClass} w-72 max-w-full`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.status} className="text-xs font-medium text-stone-600">Status</label>
          <select id={ids.status} value={status} onChange={(e) => setStatus(e.target.value as CaseStatus | "")} className={controlClass}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABEL[s]}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.channel} className="text-xs font-medium text-stone-600">Channel</label>
          <select id={ids.channel} value={channel} onChange={(e) => setChannel(e.target.value as Channel | "")} className={controlClass}>
            <option value="">All channels</option>
            {CHANNELS.map((c) => (
              <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>
            ))}
          </select>
        </div>
        {filtered ? (
          <Button
            variant="ghost"
            onClick={() => {
              setStatus("");
              setChannel("");
              setQuery("");
            }}
          >
            Clear filters
          </Button>
        ) : null}
        {data ? (
          <p className="ml-auto text-sm text-stone-500" aria-live="polite">
            Showing {plural(rows.length, "case")}
          </p>
        ) : null}
      </div>

      <Card>
        {error ? (
          <ErrorState message={errorMessage(error)} onRetry={() => mutate()} />
        ) : !data ? (
          <LoadingRows rows={8} label="Loading cases…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title={filtered ? "No matching cases" : "No cases yet"}
            hint={filtered ? "Adjust or clear the filters." : "Send a message from the Simulator to create the first case."}
          />
        ) : (
          <CaseTable cases={rows} />
        )}
      </Card>
    </>
  );
}
