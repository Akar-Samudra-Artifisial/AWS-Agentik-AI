# PRD 07 — Testing, Seed Data, Demo, dan Submission

Prefix requirement: `TST` · Milestone: M0 (seed), M3–M6 (test), M6 (demo, submit)
Prasyarat baca: semua PRD lain.

## 1. Tujuan

Memastikan demo berjalan andal, ada bukti kualitas teknis, dan paket submission lengkap sebelum tenggat.

## 2. Strategi pengujian

| Lapisan | Alat | Cakupan | Prio |
|---|---|---|---|
| Unit | pytest | Guard tool, kebijakan, util telepon, parser inbound, metrik, template, adapter (Stubber/moto) | P0 |
| Eval agen | `scripts/eval_agent.py` (Bedrock nyata) | 14 percakapan emas di `03-agent.md` §9, ≥3 kali jalan tiap kasus | P0 |
| Eval RAG | `scripts/eval_rag.py` | hit@4 pada 12 pertanyaan | P0 |
| E2E (AWS) | `scripts/e2e.py` | Skenario A, B (approve & reject), C via `/simulate/inbound` + polling API; assert status, pesan, event, approval | P0 |
| Smoke kanal nyata | manual + `send_test_message.py` | Pesan sungguhan di tiap kanal yang dipakai | P0 |
| Dashboard | manual (+ Playwright opsional) | Daftar periksa `06-dashboard.md` §8 | P0 |
| Keamanan | unit test | Tidak ada `execute_refund` tanpa approval; prompt injection tak memicu refund; penerima selalu pelanggan kasus | P0 |
| Beban ringan | skrip sederhana | 10 pesan simultan tidak merusak data (lock/dedupe) | P2 |

## 3. Data seed (`scripts/seed.py`, `make seed`)

Idempoten dan tanggal dihitung relatif terhadap "sekarang" saat seed dijalankan. Kontak demo diambil dari env.

**Pelanggan**
| ID | Nama | Kontak |
|---|---|---|
| CUST-0001 | Rani (demo) | `DEMO_PHONE_E164`, `DEMO_EMAIL` |
| CUST-0002…0005 | Pelanggan sintetis | nomor/email fiktif (tidak dikirimi pesan) |

**Pesanan untuk Rani (kurir fiktif "NusaExpress")**
| Order | Kondisi | Nilai | Dipakai untuk |
|---|---|---|---|
| ORD-1001 | `in_transit`, ETA 2 hari lalu, scan terakhir 1 hari lalu | Rp189.000 | Skenario A |
| ORD-1002 | `in_transit`, scan terakhir 6 hari lalu | Rp349.000 | Skenario B (approval) |
| ORD-1003 | `delivered` 2 hari lalu | Rp259.000 | Skenario C (eskalasi) |
| ORD-1004 | `in_transit`, tepat waktu | Rp120.000 | Tanya status |
| ORD-1005 | `in_transit`, ETA 1 hari lalu | Rp75.000 | Permintaan maaf + tracking |
| ORD-1006 | `in_transit`, scan terakhir 6 hari lalu | Rp85.000 | Auto-refund ≤Rp100.000 |
| ORD-1007 | `processing` | Rp150.000 | Perubahan alamat |
| ORD-1008 | `delivered` normal | Rp99.000 | Kontrol |

**Riwayat kasus sintetis**: ±25 kasus selesai dengan `seeded=true` tersebar 7 hari terakhir (campuran kanal, kategori, 70% `auto_resolved`, sisanya `approved_by_staff`/`escalated`, `first_response_ms` realistis 4–18 detik) agar dashboard dan metrik tidak kosong. Kasus seed memakai pelanggan sintetis agar tidak ada pesan terkirim.

## 4. Requirement

| ID | Requirement | Prio |
|---|---|---|
| TST-001 | `make seed` idempoten; `make test` menjalankan unit | P0 |
| TST-002 | `scripts/e2e.py` mengotomasi skenario A, B-approve, B-reject, C dan menghasilkan laporan lulus/gagal | P0 |
| TST-003 | Eval agen dan RAG menghasilkan laporan ringkas (tabel lulus/gagal per kasus) tersimpan di `docs/evidence/` | P0 |
| TST-004 | Daftar periksa smoke kanal nyata (§6) dijalankan dua kali: sebelum rekaman dan sebelum submit | P0 |
| TST-005 | Skrip `make demo-reset` mengembalikan data ke kondisi awal demo | P1 |
| TST-006 | Rekaman cadangan (video demo penuh) dan tangkapan layar tiap skenario | P0 |

## 5. Skrip demo (±3 menit)

| Waktu | Aksi | Yang ditonjolkan |
|---|---|---|
| 0:00–0:20 | Masalah: tiket CS berulang, chatbot biasa tidak menyelesaikan | Dampak bisnis |
| 0:20–0:50 | Dari ponsel, kirim WhatsApp skenario A; tunjukkan kasus muncul di dashboard dan linimasa agen (get_order → search_policy dengan sumber dokumen) | Agentic, RAG, real-time |
| 0:50–1:20 | Balas "1"; pesan konfirmasi WhatsApp + email diterima di ponsel | Pesan nyata multi-kanal |
| 1:20–2:05 | Skenario B: kirim keluhan hilang, pilih refund; muncul approval pending; tekan Approve; konfirmasi diterima | Human-in-the-loop, guardrail |
| 2:05–2:30 | Skenario C: ancaman polisi → eskalasi prioritas tinggi | Agen tahu batasnya |
| 2:30–3:00 | Overview: metrik; diagram arsitektur AWS; rute produk (e-commerce, logistik, telko) | Teknis + nilai |

Latih tiga kali. Siapkan ponsel dengan notifikasi aktif, layar dashboard 1080p, dan rekaman cadangan.

## 6. Daftar periksa smoke kanal nyata

- [ ] Email demo terverifikasi di SES dan menerima notifikasi.
- [ ] Nomor demo terdaftar sebagai penerima WhatsApp; pesan keluar diterima.
- [ ] Pesan WhatsApp masuk memicu dispatcher (atau Simulator sebagai cadangan, dicatat).
- [ ] SMS terkirim ke nomor yang diizinkan (jika dipakai).
- [ ] `provider_message_id` tercatat di `messages` dan log.
- [ ] Bukti disimpan di `docs/evidence/`.

## 7. Daftar periksa submission

- [ ] Persyaratan eligibility terpenuhi: APN, **ACE Opportunity ID** tercantum di formulir.
- [ ] Repo rapi: README (bahasa Inggris), diagram arsitektur, petunjuk setup, daftar layanan AWS, bagian "Real AWS messaging" dengan bukti, catatan jujur: pembayaran/kurir disimulasikan, batasan yang diketahui.
- [ ] Video demo ≤ batas yang diminta, audio jelas, memperlihatkan pesan nyata diterima.
- [ ] Deskripsi proyek: masalah, solusi, arsitektur, dampak, apa yang dibangun selama hackathon.
- [ ] Tidak ada secret/PII di repo (cek riwayat git); `.env` tidak ter-commit.
- [ ] Deploy final berjalan; URL dashboard (jika diminta) dapat dibuka; API key demo tidak disalahgunakan.
- [ ] **Submit paling lambat Rabu 28 Okt 22.00 WITA**; sisa waktu sampai tenggat resmi dipakai sebagai buffer.
- [ ] Setelah submit: pantau biaya; hancurkan resource mahal (OpenSearch Serverless) bila tidak dibutuhkan juri.

## 8. Rencana cadangan saat demo

| Masalah | Tindakan |
|---|---|
| WhatsApp tak terkirim | Lanjut dengan email + SMS; inbound via Simulator |
| Agen lambat/gagal | Putar rekaman cadangan; jalur gagal-aman akan terlihat di dashboard |
| KB error | Fallback statis aktif otomatis |
| Dashboard error | Buka kasus via API/Simulator; tunjukkan rekaman |
| Koneksi buruk | Rekaman penuh sebagai sumber utama, demo langsung sebagai bonus |
