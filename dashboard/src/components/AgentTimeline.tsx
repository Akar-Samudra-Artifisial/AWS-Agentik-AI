"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import type { AgentEvent, AgentEventType } from "@/lib/api-types";
import { formatDateTime, formatDuration, formatTime } from "@/lib/format";
import { maskText } from "@/lib/mask";
import {
  IconAlert,
  IconBolt,
  IconChat,
  IconChevronRight,
  IconDoc,
  IconEdit,
  IconPackage,
  IconSearch,
  IconSparkle,
  IconTicket,
  IconTruck,
  IconUser,
  IconWallet,
  IconX,
} from "./icons";
import { Badge } from "./StatusBadge";
import { EmptyState, SimulatedTag, cx } from "./ui";

const TYPE_LABEL: Record<AgentEventType, string> = {
  tool_call: "Tool call",
  tool_result: "Tool result",
  model_message: "Model message",
  escalation: "Escalation",
  error: "Error",
};

/** Deskripsi singkat tool agen agar langkah terbaca tanpa membuka JSON. */
const TOOL_DESCRIPTION: Record<string, string> = {
  get_order: "Look up order & tracking",
  find_orders_by_customer: "Find the customer’s orders",
  search_policy: "Search company policy (RAG)",
  update_case: "Update case category / status",
  send_message: "Reply to the customer",
  send_resolution_notice: "Send resolution notice",
  create_voucher: "Issue a goodwill voucher",
  schedule_redelivery: "Schedule a redelivery",
  request_refund: "Request a refund",
  execute_refund: "Execute an approved refund",
  escalate_to_human: "Escalate to a human agent",
};

type IconComp = (p: { className?: string }) => ReactNode;

/** Ikon per tool agar langkah mudah dipindai. */
const TOOL_ICON: Record<string, IconComp> = {
  get_order: IconPackage,
  find_orders_by_customer: IconUser,
  search_policy: IconSearch,
  update_case: IconEdit,
  send_message: IconChat,
  send_resolution_notice: IconChat,
  create_voucher: IconTicket,
  schedule_redelivery: IconTruck,
  request_refund: IconWallet,
  execute_refund: IconWallet,
  escalate_to_human: IconAlert,
};

function stepIcon(e: AgentEvent): IconComp {
  if (e.ok === false || e.type === "error") return IconX;
  const byTool = e.tool ? TOOL_ICON[e.tool] : undefined;
  if (byTool) return byTool;
  if (e.type === "escalation") return IconAlert;
  if (e.type === "model_message") return IconSparkle;
  return IconBolt;
}

const SIMULATED_TOOLS = new Set(["execute_refund", "request_refund", "schedule_redelivery"]);

/** Backend menyimpan `input`/`output` sebagai string JSON (bisa terpotong ≤4 KB); parse bila valid. */
function decode(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

/** Ambil nama dokumen sumber dari hasil `search_policy` (`[{text, source, score}]`, bisa ter-wrap). */
export function extractSources(raw: unknown): string[] {
  const output = decode(raw);
  const found = new Set<string>();
  const walk = (v: unknown, depth: number) => {
    if (depth > 4 || v == null) return;
    if (Array.isArray(v)) {
      v.forEach((x) => walk(x, depth + 1));
      return;
    }
    if (typeof v === "object") {
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        if ((k === "source" || k === "source_doc" || k === "document") && typeof val === "string") {
          found.add(val.split("/").pop() || val);
        } else {
          walk(val, depth + 1);
        }
      }
    }
  };
  walk(output, 0);
  return [...found];
}

function summarize(raw: unknown, max = 120): string {
  const value = decode(raw);
  if (value == null) return "";
  let s: string;
  if (typeof value === "string") s = value;
  else if (typeof value === "object" && !Array.isArray(value)) {
    s = Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(", ");
  } else s = JSON.stringify(value);
  s = maskText(s);
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

function pretty(raw: unknown): string {
  const value = decode(raw);
  try {
    return maskText(typeof value === "string" ? value : JSON.stringify(value, null, 2));
  } catch {
    return String(value);
  }
}

function eventKey(e: AgentEvent, i: number): string {
  return `${e.ts}#${e.seq ?? i}`;
}

export function AgentTimeline({ events }: { events: AgentEvent[] }) {
  const sorted = [...events].sort((a, b) => a.ts.localeCompare(b.ts) || (a.seq ?? 0) - (b.seq ?? 0));
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  // Sorot langkah yang baru muncul sejak render sebelumnya (bukan saat muat pertama).
  const keys = sorted.map(eventKey).join("|");
  useEffect(() => {
    const current = keys ? keys.split("|") : [];
    if (seen.current === null) {
      seen.current = new Set(current);
      return;
    }
    const added = current.filter((k) => !seen.current?.has(k));
    current.forEach((k) => seen.current?.add(k));
    if (added.length) setFresh(new Set(added));
  }, [keys]);

  if (sorted.length === 0) {
    return <EmptyState title="No agent steps yet" hint="Every tool the agent calls will be logged here." />;
  }

  return (
    <ol className="px-5 py-5" aria-label="Agent timeline">
      {sorted.map((e, i) => {
        const key = eventKey(e, i);
        const failed = e.ok === false || e.type === "error";
        const sources = e.tool === "search_policy" ? extractSources(e.output) : [];
        const detail = e.type === "tool_call" ? e.input : (e.output ?? e.input);
        const Icon = stepIcon(e);
        const last = i === sorted.length - 1;
        const tone = failed ? "danger" : e.type === "escalation" ? "warning" : e.type === "tool_result" ? "success" : "accent";
        return (
          <li key={key} className={cx("relative flex gap-3.5 rounded-lg", !last && "pb-2", fresh.has(key) && "animate-highlight")}>
            {/* Rel vertikal + node ikon per langkah. */}
            <div className="relative flex w-8 shrink-0 flex-col items-center">
              <span
                aria-hidden="true"
                className={cx(
                  "relative z-10 mt-1.5 grid size-8 place-items-center rounded-full ring-1 ring-inset [&>svg]:size-4",
                  tone === "danger" && "bg-danger-50 text-danger-600 ring-danger-200",
                  tone === "warning" && "bg-warning-50 text-warning-700 ring-warning-200",
                  tone === "success" && "bg-success-50 text-success-700 ring-success-200",
                  tone === "accent" && "bg-accent-50 text-accent-600 ring-accent-200",
                )}
              >
                <Icon />
              </span>
              {!last ? <span aria-hidden="true" className="absolute top-10 -bottom-1.5 w-px bg-zinc-200" /> : null}
            </div>
            <details className="group min-w-0 flex-1 rounded-lg px-3 py-2 transition-colors hover:bg-zinc-50 open:bg-zinc-50">
              {/* Ringkasan + sumber kebijakan selalu terlihat; JSON lengkap muncul saat dibuka. */}
              <summary className="block cursor-pointer list-none rounded [&::-webkit-details-marker]:hidden">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="font-mono text-[13px] font-semibold text-zinc-900">{e.tool ?? TYPE_LABEL[e.type] ?? e.type}</span>
                  {/* Hanya hasil tool/error yang punya status; tool_call tanpa hasil ditampilkan netral. */}
                  {failed ? (
                    <Badge tone="danger">Failed</Badge>
                  ) : e.type === "tool_result" ? (
                    <Badge tone="success">OK</Badge>
                  ) : e.type === "tool_call" ? (
                    <Badge tone="neutral" dot={false}>Called</Badge>
                  ) : e.type === "escalation" ? (
                    <Badge tone="warning">Escalation</Badge>
                  ) : null}
                  {e.tool && SIMULATED_TOOLS.has(e.tool) ? <SimulatedTag /> : null}
                  <span className="ml-auto flex items-center gap-2.5 font-mono text-[11.5px] tabular-nums text-zinc-400">
                    {e.latency_ms != null ? (
                      <span title="Latency" className="rounded bg-zinc-100 px-1.5 py-px text-zinc-600">
                        {formatDuration(e.latency_ms)}
                      </span>
                    ) : null}
                    <time dateTime={e.ts} title={formatDateTime(e.ts)}>{formatTime(e.ts)}</time>
                    <IconChevronRight aria-hidden="true" className="size-3.5 text-zinc-400 transition-transform group-open:rotate-90" />
                  </span>
                </span>
                <span className="mt-0.5 block text-xs text-zinc-500">
                  {TYPE_LABEL[e.type] ?? e.type}
                  {e.tool && TOOL_DESCRIPTION[e.tool] ? ` · ${TOOL_DESCRIPTION[e.tool]}` : ""}
                </span>
                {/* Hasil tool sukses biasanya "ok=true, …" (noise); isinya tetap ada di JSON saat dibuka. */}
                {(e.type !== "tool_result" || failed) && summarize(detail) ? (
                  <span className="mt-1.5 block font-mono text-[12px] leading-snug break-words text-zinc-600">{summarize(detail)}</span>
                ) : null}
                {sources.length ? (
                  <span className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="inline-flex items-center gap-1 font-medium text-zinc-600">
                      <IconDoc className="size-3.5 text-accent-600" />
                      Policy sources
                    </span>
                    {sources.map((src) => (
                      <span key={src} className="rounded-md bg-accent-50 px-1.5 py-0.5 font-mono text-[11.5px] text-accent-800 ring-1 ring-accent-200 ring-inset">
                        {src}
                      </span>
                    ))}
                  </span>
                ) : null}
              </summary>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {e.input != null ? <JsonBlock title="Input" value={e.input} /> : null}
                {e.output != null ? <JsonBlock title="Output" value={e.output} /> : null}
              </div>
            </details>
          </li>
        );
      })}
    </ol>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">{title}</p>
      <pre className="max-h-64 overflow-auto rounded-lg bg-zinc-950 p-3 font-mono text-[11.5px] leading-relaxed text-zinc-100 ring-1 ring-zinc-800">
        {pretty(value)}
      </pre>
    </div>
  );
}
