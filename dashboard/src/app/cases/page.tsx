"use client";

import { useId, useState } from "react";
import { CaseTable } from "@/components/CaseTable";
import { IconSearch } from "@/components/icons";
import { Button, CONTROL, Card, EmptyState, ErrorState, LoadingRows, PageHeader, SegmentedControl, Select, cx } from "@/components/ui";
import type { CaseStatus, Channel } from "@/lib/api-types";
import { errorMessage, useCases } from "@/lib/api";
import { CHANNEL_LABEL, STATUS_LABEL, plural } from "@/lib/format";

const STATUSES = Object.keys(STATUS_LABEL) as CaseStatus[];
const CHANNELS = Object.keys(CHANNEL_LABEL) as Channel[];

const CHANNEL_OPTIONS = [{ value: "" as const, label: "All" }, ...CHANNELS.map((c) => ({ value: c, label: CHANNEL_LABEL[c] }))];

export default function CasesPage() {
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [channel, setChannel] = useState<Channel | "">("");
  const [query, setQuery] = useState("");
  const ids = { status: useId(), q: useId() };
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

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-zinc-100 px-4 py-3">
          <div className="relative w-full sm:w-72">
            <label htmlFor={ids.q} className="sr-only">Search cases</label>
            <IconSearch className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-zinc-400" />
            <input
              id={ids.q}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search case, order or customer"
              className={cx(CONTROL, "w-full pr-3 pl-9")}
            />
          </div>
          <SegmentedControl name="channel" label="Channel" value={channel} options={CHANNEL_OPTIONS} onChange={setChannel} />
          <Select
            id={ids.status}
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value as CaseStatus | "")}
            className="w-full sm:w-auto"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABEL[s]}</option>
            ))}
          </Select>
          {filtered ? (
            <Button
              variant="ghost"
              size="sm"
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
            <p className="ml-auto text-[13px] text-zinc-500 tabular-nums" aria-live="polite">
              {plural(rows.length, "case")}
            </p>
          ) : null}
        </div>

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
