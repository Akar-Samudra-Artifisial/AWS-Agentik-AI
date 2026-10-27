"use client";

import { useEffect, useRef } from "react";
import type { DeliveryStatus, Message, MessageAuthor } from "@/lib/api-types";
import { formatTime } from "@/lib/format";
import { maskText } from "@/lib/mask";
import { ChannelBadge } from "./ChannelBadge";
import { EmptyState, SimulatedTag, cx } from "./ui";

const AUTHOR_LABEL: Record<MessageAuthor, string> = {
  customer: "Pelanggan",
  agent: "Agen AI",
  staff: "Staf",
  system: "Sistem",
};

const DELIVERY: Record<DeliveryStatus, { icon: string; label: string; className: string }> = {
  queued: { icon: "◌", label: "Antre", className: "text-stone-400" },
  sent: { icon: "✓", label: "Terkirim", className: "text-stone-500" },
  delivered: { icon: "✓✓", label: "Diterima", className: "text-stone-500" },
  read: { icon: "✓✓", label: "Dibaca", className: "text-sms-600" },
  failed: { icon: "!", label: "Gagal", className: "text-red-600 font-semibold" },
};

function sortKey(m: Message): string {
  return m.ts || m.created_at || "";
}

export function ChatThread({ messages }: { messages: Message[] }) {
  const listRef = useRef<HTMLOListElement>(null);
  const prevCount = useRef<number | null>(null);
  const sorted = [...messages].sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
  const count = sorted.length;

  // Thread tumbuh mengikuti isi (tanpa scroll tersembunyi). Saat ada pesan baru, gulir
  // hanya kontainer thread bila memang meluap — tidak pernah window, tidak saat muat awal.
  useEffect(() => {
    const prev = prevCount.current;
    prevCount.current = count;
    const el = listRef.current;
    if (prev == null || count <= prev || !el || el.scrollHeight <= el.clientHeight) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [count]);

  if (count === 0) {
    return <EmptyState title="Belum ada pesan" hint="Pesan masuk dan balasan agen akan muncul di sini." />;
  }

  return (
    <ol ref={listRef} className="space-y-4 overflow-y-auto px-5 py-4" aria-label="Percakapan">
      {sorted.map((m, i) => {
        const inbound = m.direction === "inbound";
        const delivery = m.delivery_status ? DELIVERY[m.delivery_status] : null;
        return (
          <li
            key={m.msg_id ?? `${sortKey(m)}-${i}`}
            className={cx("flex flex-col", inbound ? "items-start" : "items-end")}
          >
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
              <span className="font-semibold text-stone-700">{AUTHOR_LABEL[m.author] ?? m.author}</span>
              <ChannelBadge channel={m.channel} size="sm" />
              <time dateTime={m.ts}>{formatTime(m.ts)}</time>
              {m.simulated ? <SimulatedTag label="simulated" /> : null}
            </div>
            <div
              className={cx(
                "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed",
                inbound && "rounded-tl-sm bg-stone-100 text-stone-900",
                m.author === "agent" && "rounded-tr-sm bg-brand-700 text-white",
                m.author === "staff" && "rounded-tr-sm bg-stone-800 text-white",
                m.author === "system" && "rounded-tr-sm border border-dashed border-stone-300 bg-white text-stone-700",
              )}
            >
              {maskText(m.body)}
            </div>
            {!inbound && delivery ? (
              <p className={cx("mt-1 text-xs", delivery.className)}>
                <span aria-hidden="true">{delivery.icon}</span> {delivery.label}
                {m.error ? <span className="ml-1 text-red-700">— {m.error}</span> : null}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
