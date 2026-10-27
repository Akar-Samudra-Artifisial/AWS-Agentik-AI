"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useId, useState } from "react";
import { caseHref } from "@/components/CaseTable";
import { ChannelBadge } from "@/components/ChannelBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { IconArrowRight, IconRefresh, IconSend } from "@/components/icons";
import { Button, Card, CardHeader, EmptyState, PageHeader, SectionHeading, SimulatedTag, cx } from "@/components/ui";
import type { CaseSummary, Channel } from "@/lib/api-types";
import { DEMO_CUSTOMER_NAME, DEMO_PHONE_E164, errorMessage, fetchCases, resetDemo, simulateInbound, useCase } from "@/lib/api";
import { CHANNEL_LABEL, plural } from "@/lib/format";
import { maskPhone } from "@/lib/mask";
import { PRESET_MESSAGES } from "@/lib/presets";

interface Preset {
  id: string;
  title: string;
  expect: string;
  steps: string[];
}

// Teks pesan pelanggan ada di `@/lib/presets` (belum diterjemahkan, menunggu keputusan).
const PRESETS: Preset[] = [
  {
    id: "A",
    title: "A · Delivery 2 days late",
    expect: "get_order → search_policy → 3 options; reply “1” → resolved automatically",
    steps: [...PRESET_MESSAGES.A],
  },
  {
    id: "B",
    title: "B · Lost package, large refund",
    expect: "Rp349,000 > auto-limit → pending approval → Approve/Reject on the dashboard",
    steps: [...PRESET_MESSAGES.B],
  },
  {
    id: "C",
    title: "C · Marked delivered, never received",
    expect: "Legal threat → escalate_to_human (high priority)",
    steps: [...PRESET_MESSAGES.C],
  },
];

const CHANNELS: Channel[] = ["whatsapp", "sms", "email"];
const E164 = /^\+[1-9]\d{7,14}$/;
const POLL_EVERY_MS = 2000;
const POLL_MAX_MS = 45000;

type Sent = { at: string; text: string; channel: Channel; caseId: string | null; eventId: string };

export default function SimulatorPage() {
  const [customer, setCustomer] = useState<"demo" | "custom">(DEMO_PHONE_E164 ? "demo" : "custom");
  const [customPhone, setCustomPhone] = useState("");
  const [channel, setChannel] = useState<Channel>("whatsapp");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent[]>([]);
  const ids = { phone: useId(), text: useId(), channel: useId() };

  const phone = customer === "demo" ? DEMO_PHONE_E164 : customPhone.trim();
  const phoneValid = E164.test(phone);
  const canSend = phoneValid && text.trim().length > 0 && !sending;

  async function send(e?: FormEvent) {
    e?.preventDefault();
    if (!canSend) return;
    setSending(true);
    setError(null);
    const at = new Date().toISOString();
    try {
      const res = await simulateInbound({ channel, from_e164: phone, text: text.trim() });
      setSent((prev) => [{ at, text: text.trim(), channel, caseId: res?.case_id ?? null, eventId: res?.event_id ?? at }, ...prev]);
      setText("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Simulator"
        description="Trigger an inbound customer message without a phone. It is handled by the same production agent, and replies go out over the real channel to the customer’s contact."
        action={<SimulatedTag label="Simulated inbound" title="Inbound messages are injected from this page; agent replies are real" />}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <Card className="flex flex-col xl:col-span-7">
          <CardHeader icon={<IconSend />} title="Inbound message" subtitle="Compose a message as if the customer sent it." />
          <form onSubmit={send} className="flex flex-1 flex-col space-y-6 px-5 pt-5 pb-5">
            <fieldset>
              <legend className="mb-2 text-[13px] font-medium text-zinc-700">Customer</legend>
              <div className="flex flex-wrap gap-2">
                <RadioPill
                  name="customer"
                  checked={customer === "demo"}
                  disabled={!DEMO_PHONE_E164}
                  onChange={() => setCustomer("demo")}
                  label={DEMO_PHONE_E164 ? `${DEMO_CUSTOMER_NAME} · ${maskPhone(DEMO_PHONE_E164)}` : "Demo (NEXT_PUBLIC_DEMO_PHONE_E164 not set)"}
                />
                <RadioPill name="customer" checked={customer === "custom"} onChange={() => setCustomer("custom")} label="Other number" />
              </div>
              {customer === "custom" ? (
                <div className="mt-3">
                  <label htmlFor={ids.phone} className="mb-1.5 block text-xs font-medium text-zinc-600">
                    E.164 phone number (synthetic data only)
                  </label>
                  <input
                    id={ids.phone}
                    inputMode="tel"
                    value={customPhone}
                    onChange={(e) => setCustomPhone(e.target.value)}
                    placeholder="+62…"
                    aria-invalid={customPhone.length > 0 && !phoneValid}
                    aria-describedby={`${ids.phone}-hint`}
                    className="h-9 w-64 rounded-lg bg-white px-3 font-mono text-sm shadow-xs ring-1 ring-zinc-950/10 ring-inset focus:ring-2 focus:ring-accent-500 focus:outline-none aria-invalid:ring-danger-500"
                  />
                  <p id={`${ids.phone}-hint`} className="mt-1.5 text-xs text-zinc-500">
                    Unknown numbers are created as a new customer with no orders.
                  </p>
                </div>
              ) : null}
            </fieldset>

            <fieldset>
              <legend className="mb-2 text-[13px] font-medium text-zinc-700">Channel</legend>
              <div className="flex flex-wrap gap-2">
                {CHANNELS.map((c) => (
                  <RadioPill key={c} name="channel" checked={channel === c} onChange={() => setChannel(c)} label={CHANNEL_LABEL[c]} />
                ))}
              </div>
            </fieldset>

            <div>
              <label htmlFor={ids.text} className="mb-2 block text-[13px] font-medium text-zinc-700">
                Message
              </label>
              <textarea
                id={ids.text}
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
                }}
                placeholder="Type a customer message or pick a preset…"
                className="w-full rounded-lg bg-white px-3.5 py-2.5 text-[15px] leading-relaxed shadow-xs ring-1 ring-zinc-950/10 ring-inset placeholder:text-zinc-400 focus:ring-2 focus:ring-accent-500 focus:outline-none"
              />
            </div>

            {error ? (
              <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-800 ring-1 ring-danger-200 ring-inset">
                Couldn’t send: {error}
              </p>
            ) : null}

            <div className="-mx-5 -mb-5 mt-auto flex flex-wrap items-center gap-3 border-t border-zinc-100 bg-zinc-50/70 px-5 py-4">
              <Button type="submit" variant="primary" loading={sending} disabled={!canSend}>
                <IconSend />
                Send message
              </Button>
              <span className="text-xs text-zinc-500">
                or press <kbd className="rounded border border-zinc-200 bg-white px-1 font-mono text-[11px]">⌘/Ctrl</kbd> +{" "}
                <kbd className="rounded border border-zinc-200 bg-white px-1 font-mono text-[11px]">Enter</kbd>
              </span>
              {!phoneValid ? <span className="text-xs text-warning-700">Choose a customer with a valid E.164 number.</span> : null}
            </div>
          </form>
        </Card>

        <div className="space-y-6 xl:col-span-5">
          <Card>
            <CardHeader title="Scenario presets" subtitle="Fills in the message. Send the next step after the agent replies." />
            <ul className="space-y-3 p-3">
              {PRESETS.map((p) => (
                <li key={p.id} className="flex gap-3 rounded-lg p-3 ring-1 ring-zinc-950/[0.06] ring-inset">
                  <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-50 font-mono text-sm font-semibold text-accent-700 ring-1 ring-accent-200 ring-inset">
                    {p.id}
                  </span>
                  <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-zinc-900">{p.title.replace(/^[A-Z] · /, "")}</p>
                  <p className="mt-0.5 font-mono text-[11.5px] leading-snug text-zinc-500">{p.expect}</p>
                  <div className="mt-2.5 flex flex-col gap-1.5">
                    {p.steps.map((s, i) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setText(s)}
                        className="group flex max-w-full items-center gap-2 rounded-md bg-zinc-50 px-2.5 py-1.5 text-left text-xs text-zinc-700 ring-1 ring-zinc-950/[0.06] ring-inset transition-colors hover:bg-accent-50 hover:text-accent-900 hover:ring-accent-200"
                        title={s}
                      >
                        <span className="shrink-0 font-semibold text-zinc-500 group-hover:text-accent-700">Step {i + 1}</span>
                        <span className="truncate">{s}</span>
                        <IconArrowRight className="ml-auto size-3.5 shrink-0 text-zinc-300 group-hover:text-accent-600" />
                      </button>
                    ))}
                  </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <ResetDemoCard onReset={() => setSent([])} />
        </div>
      </div>

      <section aria-labelledby="sent-h" className="mt-8">
        <SectionHeading id="sent-h" title="Sent this session" count={sent.length} />
        {sent.length === 0 ? (
          <Card>
            <EmptyState title="Nothing sent yet" hint="Messages you send here will be tracked until their case appears." />
          </Card>
        ) : (
          <ul className="space-y-3">
            {sent.map((s) => (
              <SentItem key={s.eventId} sent={s} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

/** Reset data demo antar-take: hapus kasus non-seed dan kembalikan ORD-1001..1003 ke kondisi seed. */
function ResetDemoCard({ onReset }: { onReset: () => void }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);

  async function reset() {
    if (!window.confirm("Reset demo data? All non-seed cases and their messages, timelines and approvals will be deleted.")) return;
    setBusy(true);
    setStatus(null);
    try {
      const res = await resetDemo();
      setStatus({
        ok: true,
        text: `Deleted ${plural(res.deleted.cases, "case")}, ${plural(res.deleted.messages, "message")}, ${plural(res.deleted.approvals, "approval")}; orders ${res.reset_orders.join(", ")} restored.`,
      });
      onReset();
    } catch (err) {
      setStatus({ ok: false, text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader icon={<IconRefresh />} title="Reset demo" subtitle="Restore seed data before the next recording take." />
      <div className="space-y-3 px-5 py-4">
        <p className="text-xs text-zinc-500">Deletes non-seed cases, messages, timelines and approvals. You’ll be asked to confirm.</p>
        <Button variant="danger" loading={busy} onClick={() => void reset()}>
          Reset demo
        </Button>
        {status ? (
          <p role={status.ok ? "status" : "alert"} className={cx("text-xs", status.ok ? "text-success-700" : "text-danger-700")}>
            {status.text}
          </p>
        ) : null}
      </div>
    </Card>
  );
}

function RadioPill({
  name,
  checked,
  onChange,
  label,
  disabled,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={cx(
        "inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm ring-inset transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent-500",
        checked ? "bg-accent-50 font-medium text-accent-900 ring-2 ring-accent-500" : "bg-white text-zinc-700 shadow-xs ring-1 ring-zinc-950/10 hover:bg-zinc-50",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <input type="radio" name={name} checked={checked} onChange={onChange} disabled={disabled} className="accent-accent-600" />
      {label}
    </label>
  );
}

/** Tampilkan tautan kasus; bila API tidak mengembalikan case_id, poll daftar kasus sampai kasus muncul. */
function SentItem({ sent }: { sent: Sent }) {
  const [found, setFound] = useState<CaseSummary | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const caseId = sent.caseId ?? found?.case_id ?? null;
  const detail = useCase(caseId);

  useEffect(() => {
    if (sent.caseId) return;
    let cancelled = false;
    let timer: number | undefined;
    const tick = async () => {
      try {
        const list = await fetchCases(20);
        const hit = list.find((c) => c.updated_at >= sent.at);
        if (!cancelled && hit) {
          setFound(hit);
          return;
        }
      } catch {
        // abaikan; coba lagi sampai batas waktu
      }
      if (cancelled) return;
      if (Date.now() - Date.parse(sent.at) > POLL_MAX_MS) setTimedOut(true);
      else timer = window.setTimeout(tick, POLL_EVERY_MS);
    };
    void tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sent.caseId, sent.at]);

  const status = detail.data?.case.status ?? found?.status;

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl bg-white px-4 py-3 shadow-card ring-1 ring-zinc-950/[0.06]">
      <ChannelBadge channel={sent.channel} />
      <p className="min-w-0 flex-1 truncate text-sm text-zinc-800" title={sent.text}>
        “{sent.text}”
      </p>
      {caseId ? (
        <>
          {status ? <StatusBadge status={status} /> : null}
          <Link href={caseHref(caseId)} className="font-mono text-[13px] font-medium text-accent-700 hover:underline">
            Open {caseId} →
          </Link>
        </>
      ) : timedOut ? (
        <span className="text-sm text-warning-700">Case hasn’t appeared yet. Check the Cases page.</span>
      ) : (
        <span role="status" className="text-sm text-zinc-500">Waiting for the case to be created…</span>
      )}
    </li>
  );
}
