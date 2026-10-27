# PRD 02 — Backend (Lambda dispatcher + API)

Prefix requirement: `BE` · Milestone: M0 (common), M4 (dispatcher, API)
Prasyarat baca: `00-overview.md` §8, §10.

## 1. Tujuan

Menjadi lapisan orkestrasi: menerima pesan masuk, memelihara kasus, memanggil agen, melayani dashboard, dan menjalankan alur approval. **Backend tidak membuat keputusan bisnis**; keputusan ada di agen dan guard di tool.

## 2. Komponen

| Komponen | Pemicu | Tugas |
|---|---|---|
| `packages/common` | — | models pydantic, repositori DynamoDB, `policy.py`, util nomor telepon (E.164), logging JSON, adapter pesan (lihat `05-messaging.md`) |
| Lambda `dispatcher` | SNS (WhatsApp inbound/status) dan invoke async dari `api` | Normalisasi, dedupe, upsert pelanggan/kasus, simpan pesan, lock, panggil AgentCore Runtime, jalur gagal-aman |
| Lambda `api` | API Gateway HTTP API | REST untuk dashboard, metrik, approval, simulator |

Struktur: `backend/app/{api,dispatcher,services}/`, `backend/tests/`.

## 3. Requirement

| ID | Requirement | Prio |
|---|---|---|
| BE-001 | `packages/common`: model pydantic v2 untuk semua entitas di `00-overview.md` §10 beserta enum | P0 |
| BE-002 | Repositori DynamoDB per tabel (get/put/update/query), konversi `Decimal`↔`int`, serialisasi JSON aman | P0 |
| BE-003 | Util `normalize_phone()` ke E.164 (Indonesia: `0812…` → `+62812…`), `mask_phone()` untuk log | P0 |
| BE-004 | Parser event inbound WhatsApp dari SNS → `NormalizedInbound` (lihat §4). Tulis dari fixture event nyata yang di-log pertama kali | P0 |
| BE-005 | Dispatcher: alur §4 lengkap termasuk dedupe (`processed_events`) | P0 |
| BE-006 | Pencarian/pembuatan kasus: pakai kasus milik pelanggan dengan status bukan `resolved/escalated/error` dan `updated_at` dalam `CASE_REUSE_WINDOW_HOURS`; selain itu buat kasus baru (`CASE-YYYYMMDD-xxxx`) | P0 |
| BE-007 | Lock per kasus via update bersyarat `lock_until` (TTL 150 s); jika terkunci, simpan pesan dan set flag `pending_followup`; setelah giliran selesai, jalankan satu giliran lanjutan | P1 (P0: tolak giliran paralel dengan aman) |
| BE-008 | Invoke AgentCore Runtime (`bedrock-agentcore` `invoke_agent_runtime`), `runtimeSessionId` stabil per kasus dan panjang ≥33 karakter (mis. `case-<case_id>-<padding>`), timeout klien 120 s | P0 |
| BE-009 | Jalur gagal-aman (§7) | P0 |
| BE-010 | API endpoints §5 dengan validasi pydantic, header `x-api-key`, error format seragam | P0 |
| BE-011 | `POST /api/approvals/{id}/decision` idempoten dan async (balas 202 cepat) | P0 |
| BE-012 | `GET /api/metrics` sesuai definisi §6 | P0 |
| BE-013 | Handler status pengiriman WhatsApp → update `messages.delivery_status` | P1 |
| BE-014 | `POST /api/demo/reset` (hapus data non-seed, re-seed) | P1 |
| BE-015 | `POST /api/cases/{id}/messages` (balasan staf manual lewat adapter) | P2 |
| BE-016 | OpenAPI otomatis dari FastAPI untuk generate tipe dashboard | P0 |

## 4. Alur dispatcher

Input: event SNS **atau** payload langsung `{type: "simulate_inbound" | "approval_decided", ...}`.

1. Tentukan sumber dan `event_id` (WhatsApp: ID pesan Meta; simulate: UUID dari API; approval: `approval_id#decided_at`).
2. Dedupe: `put_item` bersyarat ke `processed_events`; jika sudah ada → selesai (SNS at-least-once).
3. Normalisasi ke `NormalizedInbound{event_id, channel, from_e164, text, received_at, provider_message_id, simulated}`.
4. Upsert pelanggan lewat `by_phone`; nomor tak dikenal → buat pelanggan "Pelanggan baru" tanpa pesanan.
5. Cari/buat kasus (BE-006). Simpan pesan inbound; set `first_inbound_at` bila kosong.
6. Ambil lock (BE-007).
7. Bangun payload agen (kontrak §8), sertakan 20 pesan terakhir.
8. Invoke AgentCore Runtime (BE-008).
9. Lepas lock. Tool agen sudah menulis perubahan kasus, pesan, dan event; dispatcher hanya mencatat hasil di log.
10. Untuk `approval_decided`: lewati langkah 3–5, pakai kasus dari approval.

## 5. Kontrak API (bekukan sebelum M5)

Semua endpoint di bawah `/api`, header `x-api-key`. Waktu ISO 8601 UTC.

| Metode | Path | Deskripsi | Respons |
|---|---|---|---|
| GET | `/health` | Cek hidup | `{status:"ok"}` |
| GET | `/cases?status=&channel=&limit=50` | Daftar kasus, terbaru dulu | `CaseSummary[]` (id, status, category, priority, channel, customer_name, order_id, summary, updated_at, resolution_type) |
| GET | `/cases/{case_id}` | Detail | `CaseDetail`: kasus + `customer` + `order` + `messages[]` + `events[]` + `approvals[]` |
| GET | `/approvals?status=pending` | Antrean approval | `Approval[]` (dengan ringkasan kasus) |
| POST | `/approvals/{approval_id}/decision` | Body `{decision:"approve"|"reject", note?, decided_by}` | 202 `{approval_id, status}`; 409 jika sudah diputuskan |
| POST | `/simulate/inbound` | Body `{channel, from_e164, text}` | 202 `{event_id, case_id?}` |
| GET | `/metrics` | Metrik agregat | §6 |
| POST | `/demo/reset` | Reset data demo (P1) | 200 |
| POST | `/cases/{case_id}/messages` | Balasan staf (P2) | 202 |

Error: `{error:{code,message}}` dengan kode HTTP yang tepat (400/401/404/409/500).

## 6. Definisi metrik

```json
{
  "totals": {"cases": 0, "active": 0, "resolved": 0, "escalated": 0, "pending_approvals": 0},
  "auto_resolution_rate": 0.0,
  "first_response_ms": {"p50": 0, "p90": 0},
  "resolution_ms": {"p50": 0},
  "by_channel": {"whatsapp": 0, "sms": 0, "email": 0},
  "by_category": {"late_delivery": 0},
  "messages_sent": {"whatsapp": 0, "sms": 0, "email": 0}
}
```

- `auto_resolution_rate` = kasus `resolution_type=auto_resolved` ÷ kasus berstatus `resolved` atau `escalated`.
- `first_response_ms` = `first_response_at − first_inbound_at` (kasus yang punya keduanya).
- `resolution_ms` = `resolved_at − first_inbound_at`.
- `active` = status `open|investigating|awaiting_customer|awaiting_approval`.
- Data seed ikut dihitung (agar dashboard tidak kosong); tandai `seeded` di data, tidak di UI.
- Volume kecil: boleh `Scan`/`Query` penuh dan hitung di memori.

## 7. Jalur gagal-aman

Jika invoke agen gagal atau timeout:
1. Set kasus `error`, tulis `agent_events(type=error)`.
2. Kirim pesan ke pelanggan lewat adapter ("Maaf, ada kendala teknis. Tim kami akan segera menghubungi Anda.") sekali saja per kasus.
3. Buat catatan eskalasi (`status=escalated`, `priority=high`) agar muncul di dashboard.

## 8. Kontrak invocation agen (dikonsumsi `03-agent.md`)

```json
{
  "event_type": "customer_message | approval_decided",
  "case_id": "CASE-20261028-0001",
  "customer": {"customer_id": "", "name": "", "phone_e164": "", "email": "", "language": "id", "preferred_channel": "whatsapp"},
  "channel": "whatsapp",
  "message": {"text": "", "received_at": ""},
  "history": [{"direction": "inbound", "author": "customer", "channel": "whatsapp", "body": "", "ts": ""}],
  "approval": {"approval_id": "", "status": "approved|rejected", "note": ""}
}
```

Respons agen: `{case_id, case_status, category, actions:[{tool, ok}], error}`.

## 9. Pengujian

- Unit: parser inbound (fixture), normalisasi telepon, pemilihan kasus, dedupe, metrik, validasi endpoint (pytest + moto/Stubber).
- Integrasi: dispatcher dengan agen di-stub mengembalikan respons tetap.
- Kontrak: snapshot OpenAPI; dashboard memakai tipe hasil generate.

## 10. Acceptance criteria

- [ ] Event SNS yang sama dikirim 2× hanya diproses sekali.
- [ ] `POST /simulate/inbound` membuat kasus, menyimpan pesan, dan memicu agen; respons <1 detik.
- [ ] Approval keputusan ganda mengembalikan 409 dan tidak memicu agen dua kali.
- [ ] Kegagalan agen menghasilkan pesan gagal-aman + kasus `escalated`.
- [ ] `GET /metrics` konsisten dengan data (test dengan fixture).
- [ ] Tidak ada nomor telepon penuh di log.
