"use client";

import { useEffect, useRef, useState } from "react";
import type { AgentEvent, AgentEventType } from "@/lib/api-types";
import { formatDuration, formatTime } from "@/lib/format";
import { maskText } from "@/lib/mask";
import { EmptyState, SimulatedTag, cx } from "./ui";

const TYPE_LABEL: Record<AgentEventType, string> = {
  tool_call: "Tool call",
  tool_result: "Hasil tool",
  model_message: "Pesan model",
  escalation: "Eskalasi",
  error: "Error",
};

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
    return <EmptyState title="Agen belum mengambil langkah" hint="Setiap tool call agen akan tercatat di sini." />;
  }

  return (
    <ol className="relative space-y-1 px-5 py-4" aria-label="Linimasa agen">
      {sorted.map((e, i) => {
        const key = eventKey(e, i);
        const failed = e.ok === false || e.type === "error";
        const sources = e.tool === "search_policy" ? extractSources(e.output) : [];
        const detail = e.type === "tool_call" ? e.input : (e.output ?? e.input);
        return (
          <li key={key} className={cx("relative rounded-lg pl-7", fresh.has(key) && "animate-highlight")}>
            <span
              aria-hidden="true"
              className={cx(
                "absolute top-3 left-1.5 size-2.5 rounded-full ring-4 ring-white",
                failed ? "bg-red-600" : e.type === "escalation" ? "bg-amber-500" : "bg-brand-600",
              )}
            />
            {i < sorted.length - 1 ? (
              <span aria-hidden="true" className="absolute top-6 bottom-[-6px] left-[10px] w-px bg-stone-200" />
            ) : null}
            <details className="group rounded-lg px-2 py-2 hover:bg-stone-50">
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-2 gap-y-1 rounded">
                <span className="font-mono text-sm font-semibold text-stone-900">
                  {e.tool ?? TYPE_LABEL[e.type] ?? e.type}
                </span>
                <span className="text-xs text-stone-500">{TYPE_LABEL[e.type] ?? e.type}</span>
                <span
                  className={cx(
                    "rounded px-1.5 text-[11px] font-medium",
                    failed ? "bg-red-100 text-red-800" : "bg-emerald-50 text-emerald-800",
                  )}
                >
                  {failed ? "✕ gagal" : "✓ ok"}
                </span>
                {e.tool && SIMULATED_TOOLS.has(e.tool) ? <SimulatedTag /> : null}
                <span className="ml-auto flex items-center gap-2 text-xs tabular-nums text-stone-500">
                  {e.latency_ms != null ? <span>{formatDuration(e.latency_ms)}</span> : null}
                  <time dateTime={e.ts}>{formatTime(e.ts)}</time>
                  <span aria-hidden="true" className="transition-transform group-open:rotate-90">
                    ›
                  </span>
                </span>
              </summary>
              {summarize(detail) ? (
                <p className="mt-1 text-[13px] leading-snug text-stone-600">{summarize(detail)}</p>
              ) : null}
              {sources.length ? (
                <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="font-medium text-stone-600">Sumber kebijakan:</span>
                  {sources.map((s) => (
                    <span key={s} className="rounded bg-brand-50 px-1.5 py-0.5 font-mono text-brand-700 ring-1 ring-brand-100">
                      {s}
                    </span>
                  ))}
                </p>
              ) : null}
              <div className="mt-2 grid gap-2 lg:grid-cols-2">
                {e.input != null ? <JsonBlock title="input" value={e.input} /> : null}
                {e.output != null ? <JsonBlock title="output" value={e.output} /> : null}
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
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-stone-500">{title}</p>
      <pre className="max-h-64 overflow-auto rounded-md bg-stone-900 p-3 font-mono text-xs leading-relaxed text-stone-100">
        {pretty(value)}
      </pre>
    </div>
  );
}
