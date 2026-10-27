"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useId, useState } from "react";
import { caseHref } from "@/components/CaseTable";
import { ChannelBadge } from "@/components/ChannelBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Button, Card, CardHeader, PageHeader, SimulatedTag, cx } from "@/components/ui";
import type { CaseSummary, Channel } from "@/lib/api-types";
import { DEMO_CUSTOMER_NAME, DEMO_PHONE_E164, errorMessage, fetchCases, resetDemo, simulateInbound, useCase } from "@/lib/api";
import { CHANNEL_LABEL } from "@/lib/format";
import { maskPhone } from "@/lib/mask";

interface Preset {
  id: string;
  title: string;
  expect: string;
  steps: string[];
}

// Teks dari docs/prd/00-overview.md §7 (skenario A/B/C).
const PRESETS: Preset[] = [
  {
    id: "A",
    title: "A · Terlambat 2 hari",
    expect: "get_order → search_policy → 3 opsi; balas “1” → resolved (auto)",
    steps: ["Pesanan ORD-1001 saya terlambat 2 hari.", "1"],
  },
  {
    id: "B",
    title: "B · Paket hilang, refund besar",
    expect: "Rp349.000 > batas → approval pending → Approve/Reject di dashboard",
    steps: ["ORD-1002 belum sampai juga, sudah seminggu.", "Saya pilih refund saja."],
  },
  {
    id: "C",
    title: "C · Delivered tapi tidak diterima",
    expect: "Ancaman hukum → escalate_to_human (prioritas tinggi)",
    steps: ["ORD-1003 katanya sudah diterima tapi saya tidak terima apa-apa. Saya akan lapor polisi!"],
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
        description="Picu pesan masuk tanpa ponsel. Pesan diproses agen yang sama; balasan agen dikirim lewat kanal nyata ke kontak pelanggan."
        action={<SimulatedTag label="inbound simulated" />}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader title="Pesan masuk" />
          <form onSubmit={send} className="space-y-5 px-5 py-5">
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-stone-700">Pelanggan</legend>
              <div className="flex flex-wrap gap-2">
                <RadioPill
                  name="customer"
                  checked={customer === "demo"}
                  disabled={!DEMO_PHONE_E164}
                  onChange={() => setCustomer("demo")}
                  label={DEMO_PHONE_E164 ? `${DEMO_CUSTOMER_NAME} · ${maskPhone(DEMO_PHONE_E164)}` : "Demo (NEXT_PUBLIC_DEMO_PHONE_E164 kosong)"}
                />
                <RadioPill name="customer" checked={customer === "custom"} onChange={() => setCustomer("custom")} label="Nomor lain" />
              </div>
              {customer === "custom" ? (
                <div className="mt-3">
                  <label htmlFor={ids.phone} className="mb-1 block text-xs font-medium text-stone-600">
                    Nomor E.164 (data sintetis)
                  </label>
                  <input
                    id={ids.phone}
                    inputMode="tel"
                    value={customPhone}
                    onChange={(e) => setCustomPhone(e.target.value)}
                    placeholder="+62…"
                    aria-invalid={customPhone.length > 0 && !phoneValid}
                    aria-describedby={`${ids.phone}-hint`}
                    className="w-64 rounded-lg border border-stone-300 px-3 py-2 font-mono text-sm focus:border-brand-600 aria-invalid:border-red-500"
                  />
                  <p id={`${ids.phone}-hint`} className="mt-1 text-xs text-stone-500">
                    Nomor tak dikenal akan dibuat sebagai “Pelanggan baru” tanpa pesanan.
                  </p>
                </div>
              ) : null}
            </fieldset>

            <fieldset>
              <legend className="mb-2 text-sm font-medium text-stone-700">Kanal</legend>
              <div className="flex flex-wrap gap-2">
                {CHANNELS.map((c) => (
                  <RadioPill key={c} name="channel" checked={channel === c} onChange={() => setChannel(c)} label={CHANNEL_LABEL[c]} />
                ))}
              </div>
            </fieldset>

            <div>
              <label htmlFor={ids.text} className="mb-1 block text-sm font-medium text-stone-700">
                Isi pesan
              </label>
              <textarea
                id={ids.text}
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
                }}
                placeholder="Tulis pesan pelanggan atau pilih preset…"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-[15px] focus:border-brand-600"
              />
            </div>

            {error ? (
              <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                Gagal mengirim: {error}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="primary" loading={sending} disabled={!canSend}>
                Kirim pesan
              </Button>
              <span className="text-xs text-stone-500">⌘/Ctrl + Enter</span>
              {!phoneValid ? <span className="text-xs text-amber-700">Pilih pelanggan dengan nomor E.164 yang valid.</span> : null}
            </div>
          </form>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Preset skenario" subtitle="Isi otomatis teks; kirim langkah berikutnya setelah agen membalas." />
            <ul className="divide-y divide-stone-100">
              {PRESETS.map((p) => (
                <li key={p.id} className="px-5 py-3.5">
                  <p className="font-medium text-stone-900">{p.title}</p>
                  <p className="mt-0.5 text-xs text-stone-500">{p.expect}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {p.steps.map((s, i) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setText(s)}
                        className="max-w-full truncate rounded-md border border-stone-300 bg-stone-50 px-2.5 py-1 text-left text-xs text-stone-700 hover:border-brand-600 hover:bg-brand-50"
                        title={s}
                      >
                        <span className="font-semibold">Langkah {i + 1}:</span> {s}
                      </button>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <ResetDemoCard onReset={() => setSent([])} />
        </div>
      </div>

      <section aria-labelledby="sent-h" className="mt-8">
        <h2 id="sent-h" className="mb-3 text-[15px] font-semibold text-stone-900">Terkirim di sesi ini</h2>
        {sent.length === 0 ? (
          <p className="text-sm text-stone-500">Belum ada pesan yang dikirim.</p>
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
    if (!window.confirm("Reset data demo? Semua kasus non-seed beserta pesan, timeline, dan approval-nya akan dihapus.")) return;
    setBusy(true);
    setStatus(null);
    try {
      const res = await resetDemo();
      setStatus({
        ok: true,
        text: `Dihapus ${res.deleted.cases} kasus, ${res.deleted.messages} pesan, ${res.deleted.approvals} approval; pesanan ${res.reset_orders.join(", ")} direset.`,
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
      <CardHeader title="Reset demo" subtitle="Kembalikan data ke kondisi awal sebelum take rekaman berikutnya." />
      <div className="space-y-3 px-5 py-4">
        <Button variant="danger" loading={busy} onClick={() => void reset()}>
          Reset demo
        </Button>
        {status ? (
          <p role={status.ok ? "status" : "alert"} className={cx("text-xs", status.ok ? "text-stone-600" : "text-red-700")}>
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
        "inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand-600",
        checked ? "border-brand-600 bg-brand-50 text-brand-900" : "border-stone-300 bg-white text-stone-700 hover:bg-stone-50",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <input type="radio" name={name} checked={checked} onChange={onChange} disabled={disabled} className="accent-brand-700" />
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
    <li className="flex flex-wrap items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 shadow-sm">
      <ChannelBadge channel={sent.channel} />
      <p className="min-w-0 flex-1 truncate text-sm text-stone-800" title={sent.text}>
        “{sent.text}”
      </p>
      {caseId ? (
        <>
          {status ? <StatusBadge status={status} /> : null}
          <Link href={caseHref(caseId)} className="font-mono text-sm font-medium text-brand-700 hover:underline">
            Buka {caseId} →
          </Link>
        </>
      ) : timedOut ? (
        <span className="text-sm text-amber-700">Kasus belum muncul. Cek halaman Kasus.</span>
      ) : (
        <span role="status" className="text-sm text-stone-500">Menunggu kasus terbentuk…</span>
      )}
    </li>
  );
}
