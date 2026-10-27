# PRD 05 — Messaging (WhatsApp, SMS, Email)

Prefix requirement: `MSG` · Milestone: M1 (adapter), M4 (inbound)
Prasyarat baca: `00-overview.md` §7, §10; `03-agent.md` §5.

## 1. Tujuan

Mengirim dan menerima pesan **nyata** lewat layanan AWS. Ini persyaratan eksplisit hackathon: SDK AWS harus dipakai untuk mengirim pesan sungguhan di runtime, bukan hanya disebut di README atau disimulasikan di kode.

## 2. Layanan dan klien boto3

| Kanal | Layanan | Klien boto3 | Operasi |
|---|---|---|---|
| WhatsApp (keluar) | AWS End User Messaging Social | `socialmessaging` | `send_whatsapp_message` |
| WhatsApp (masuk, status) | End User Messaging Social → SNS | — | event ke SNS `inbound-whatsapp` |
| SMS (keluar) | AWS End User Messaging SMS | `pinpoint-sms-voice-v2` | `send_text_message` |
| Email (keluar) | Amazon SES | `sesv2` | `send_email` |

Cakupan MVP: WhatsApp dua arah; SMS dan email hanya keluar. Email masuk dan SMS dua arah di luar cakupan. Nama klien/operasi ditulis dari ingatan: **konfirmasi** dengan dokumentasi/`boto3` saat implementasi.

## 3. Requirement

| ID | Requirement | Prio |
|---|---|---|
| MSG-001 | Antarmuka adapter di `packages/common/messaging/`: `send_whatsapp(to_e164, text)`, `send_sms(to_e164, text)`, `send_email(to, subject, html, text)`, semua mengembalikan `SendResult{ok, channel, provider_message_id, error, raw}`. Tidak melempar exception ke pemanggil | P0 |
| MSG-002 | **Email (SES)**: `sesv2.send_email` dengan `FromEmailAddress` dari SSM, `Content.Simple` (Subject, Body Html + Text) | P0 |
| MSG-003 | **WhatsApp**: `socialmessaging.send_whatsapp_message(originationPhoneNumberId, metaApiVersion, message=<bytes JSON>)`; payload Meta: `{"messaging_product":"whatsapp","to":"<E.164>","type":"text","text":{"body":"…"}}` | P0 |
| MSG-004 | **SMS**: `send_text_message(DestinationPhoneNumber, OriginationIdentity, MessageBody, MessageType="TRANSACTIONAL")` | P0 (minimal sebagai fallback) |
| MSG-005 | Pemilihan kanal dan fallback (§4) | P0 |
| MSG-006 | Template notifikasi deterministik (`send_resolution_notice`, §5) | P0 |
| MSG-007 | Setiap pengiriman menulis `messages` (outbound, `provider_message_id`, `delivery_status=sent|failed`, `error`) dan mengisi `cases.first_response_at` pada outbound pertama | P0 |
| MSG-008 | Parser inbound WhatsApp: log event SNS mentah pertama kali, simpan sebagai fixture di `tests/fixtures/`, tulis parser dari fixture itu; ambil teks, nomor pengirim, ID pesan | P0 |
| MSG-009 | Normalisasi nomor ke E.164; tolak/log nomor tak valid | P0 |
| MSG-010 | `scripts/send_test_message.py --channel whatsapp|sms|email --to …` untuk uji manual dan bukti | P0 |
| MSG-011 | Status pengiriman WhatsApp (sent/delivered/read/failed) dari event SNS → update `delivery_status` | P1 |
| MSG-012 | Retry dengan backoff untuk error sementara (throttling), maks 2 percobaan | P1 |
| MSG-013 | Configuration set SES + event destination untuk status email | P2 |

## 4. Pemilihan kanal dan fallback

- Balasan percakapan: **kanal yang dipakai pelanggan** (inbound).
- Konfirmasi akhir (`send_resolution_notice`): kanal inbound **+ email** jika pelanggan punya email.
- Fallback bila pengiriman gagal: WhatsApp → SMS → email. Catat tiap percobaan di `messages` dan `agent_events`.
- Jendela layanan WhatsApp: balasan teks bebas hanya diizinkan dalam 24 jam sejak pesan terakhir pelanggan. Pesan proaktif di luar jendela memerlukan template yang disetujui Meta → untuk MVP, jika di luar jendela, langsung pakai SMS/email.
- Pesan ke simulator: kanal tetap dicatat sebagai kanal asli, tapi pengiriman keluar tetap **nyata** ke nomor/email demo pelanggan.

## 5. Template notifikasi (deterministik)

Ditulis dalam `packages/common/messaging/templates/` (Bahasa Indonesia, versi Inggris P2). Parameter: `case_id`, `customer_name`, `summary`, `next_steps`, `voucher_code?`.

| Kanal | Format | Batas |
|---|---|---|
| WhatsApp | Teks singkat: salam, ringkasan tindakan, langkah berikutnya, kode kasus | ≤600 karakter |
| SMS | Satu kalimat + kode kasus, tanpa emoji | ≤160 karakter bila memungkinkan; log jumlah segmen |
| Email | HTML sederhana (kartu ringkasan: kode kasus, tindakan, nominal/voucher, langkah berikutnya) + alternatif teks | subject: `[ResolveAI] Kasus <case_id> telah diselesaikan` |

Pesan percakapan lain (opsi, pertanyaan) ditulis oleh agen lewat `send_message`; hanya notifikasi akhir yang pakai template agar konsisten.

## 5a. Bukti pesan nyata (untuk juri)

- Simpan di `docs/evidence/`: tangkapan layar pesan diterima (WhatsApp, SMS, email), potongan log CloudWatch dengan `provider_message_id`, dan keluaran `send_test_message.py`.
- Tautkan di README bagian "Real AWS messaging".

## 6. Kendala sandbox dan risiko

- **SES sandbox**: hanya alamat/domain terverifikasi yang bisa menerima.
- **SMS sandbox**: nomor tujuan harus diverifikasi; cek aturan registrasi sender ID untuk Indonesia; jika tidak memungkinkan, SMS tidak dipakai di demo (tetap diimplementasikan dan diuji ke nomor yang bisa).
- **WhatsApp**: sebelum verifikasi bisnis Meta selesai, pengiriman terbatas ke penerima terdaftar/uji. Daftarkan nomor demo di awal. Jika WABA tidak siap, demo memakai email + SMS dan inbound lewat Simulator.
- Skema event SNS WhatsApp: jangan berasumsi; lihat event mentah (MSG-008).

## 7. Pengujian

- Unit (tanpa jaringan): adapter dengan `botocore.stub.Stubber`; format payload WhatsApp; parser dengan fixture; fallback chain; template (panjang, placeholder).
- Integrasi manual (M1, M6): `send_test_message.py` ke tiap kanal, catat bukti.
- Smoke test di M6: skenario A dan B dengan pesan nyata.

## 8. Acceptance criteria

- [ ] Email nyata terkirim via SES dan diterima.
- [ ] WhatsApp nyata terkirim dan diterima (atau SMS nyata bila WABA belum siap; catat di STATUS.md).
- [ ] Pesan WhatsApp masuk memicu dispatcher dan membuka kasus (atau Simulator sebagai cadangan).
- [ ] Kegagalan satu kanal memicu fallback dan tercatat.
- [ ] Tidak ada kode non-test yang membuat pengiriman palsu.
- [ ] Event SNS duplikat tidak menghasilkan balasan ganda.
