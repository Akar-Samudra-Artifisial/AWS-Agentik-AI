# Demo Video Script — ResolveAI (≤ 3:00)

Submission: **AWS CDS Agentic AI Hackathon - Sept. 2026**. Video target 2:55, maksimum 3:00.

Fakta yang boleh diklaim di video:
- CDS nyata: **Amazon SES (email)** via AWS SDK. WhatsApp (EUM Social) dan SMS **tidak** ditampilkan sebagai berjalan — adapter ada, tetapi WABA belum aktif dan SMS belum diuji.
- Inbound pelanggan disimulasikan lewat halaman `/simulator` (kanal `email`); balasan agen terkirim sebagai email SES sungguhan.
- Agen: Strands Agents di Amazon Bedrock AgentCore Runtime (Claude Sonnet 4.5), RAG via Bedrock Knowledge Base (Titan Embeddings V2 + S3 Vectors, eval hit@4 93,8%).
- Guard refund ada di kode tool (`execute_refund` hanya jalan bila approval `approved` di DynamoDB), bukan di prompt.
- Pembayaran dan kurir **simulated** — katakan dengan jujur.

## 1. Timeline

| Waktu | Di layar | Narasi (EN) | Aksi klik |
|---|---|---|---|
| 0:00–0:15 | Judul + dashboard `/` (metrik) | "Customer-service teams answer the same complaints every day — late parcels, lost packages, refunds. Scripted chatbots reply, but they don't resolve. ResolveAI is an agentic recovery agent that actually takes action." | Buka `/`, diam di kartu metrik |
| 0:15–0:30 | Diagram `docs/architecture.md` | "It runs fully on AWS: API Gateway and Lambda, a Strands agent on Bedrock AgentCore Runtime with Claude Sonnet 4.5, a Bedrock Knowledge Base for policies, DynamoDB for state, and Amazon SES to reach the customer." | Tampilkan diagram (render Mermaid di GitHub) |
| 0:30–0:45 | `/simulator`, kanal `email`, preset A | "For this demo, inbound messages come from our simulator on the email channel. Payments and the courier are simulated; the emails are real." | Pilih kanal `email` → preset **A** → Kirim langkah 1 ("Pesanan ORD-1001 saya terlambat 2 hari.") |
| 0:45–1:10 | `/case/?id=…` kasus A: timeline agen | "The agent looks up the order, sees it is two days late, and searches the policy knowledge base — here is the source document it cited. It apologises and offers options." | Buka kasus baru dari `/cases/`; sorot `get_order` → `search_policy` + sumber dokumen |
| 1:10–1:25 | Tab Gmail inbox demo | "And this is the real email delivered by Amazon SES, seconds later." | Pindah ke Gmail, buka email terbaru |
| 1:25–1:35 | `/simulator` preset A langkah 2 → kasus A | "The customer picks option 1, and the case is resolved automatically." | Kirim "1"; tunjukkan status kasus berubah |
| 1:35–1:55 | `/simulator` preset B → kasus B | "Scenario B: a lost parcel worth 349,000 rupiah. The customer asks for a refund. Our auto-refund limit is 100,000, so the agent cannot pay it out — it requests approval instead." | Preset **B**, kirim langkah 1, tunggu balasan, kirim langkah 2 ("Saya pilih refund saja."); buka kasus, sorot approval `pending` |
| 1:55–2:15 | `/approvals/` → Approve → kasus B + Gmail | "This guardrail lives in the tool code, not in the prompt: execute_refund only runs when an approval is marked approved in DynamoDB. A staff member approves, the simulated refund executes, and the customer gets a resolution email." | Klik **Approve**; tunjukkan `execute_refund` di timeline + email resolusi di Gmail |
| 2:15–2:20 | (overlay teks) | "If staff reject, the refund is never executed and the case is escalated." | Tidak ada klik (opsional potong singkat take reject) |
| 2:20–2:40 | `/simulator` preset C → kasus C | "Scenario C: the courier says delivered, the customer says nothing arrived and threatens to call the police. The agent knows its limits — it escalates to a human with high priority." | Preset **C**, kirim; buka kasus, sorot `escalate_to_human` + prioritas `high` |
| 2:40–2:55 | `/` metrik + `/cases/` | "Every step is observable: tool timeline, cited policy sources, approvals and delivery status per message. ResolveAI fits e-commerce, logistics and telco support. Thank you." | Kembali ke `/`, scroll metrik |

Total: **2:55** (buffer 5 detik).

## 2. Persiapan sebelum rekam

1. Buka `https://dhv2ziygcntil.cloudfront.net/simulator/` → klik **Reset demo** → konfirmasi (hapus kasus non-seed, ORD-1001..1003 kembali ke kondisi seed). Ulangi sebelum tiap take.
2. Pastikan kanal Simulator = `email` dan kontak pelanggan demo terisi (dari env, jangan tampilkan alamat penuh di layar).
3. Pemanasan: kirim satu pesan uji lalu Reset lagi agar runtime AgentCore tidak cold start saat rekam.
4. Urutan tab browser:
   1. Dashboard `/` (overview)
   2. `/simulator/`
   3. `/cases/` (buka kasus dari sini)
   4. `/approvals/`
   5. Gmail inbox demo (sembunyikan alamat email / blur saat edit)
   6. Diagram arsitektur (`docs/architecture.md` di GitHub)
   7. Opsional: AWS console (AgentCore Runtime, SES sending statistics) untuk b-roll
5. Layar 1080p, zoom browser 110–125%, notifikasi OS mati, mikrofon dites.
6. Rekam tiap skenario sebagai take terpisah lalu sambung; simpan rekaman cadangan (lihat PRD 07 §8).

## 3. Poin yang dinilai juri (pastikan terlihat)

| Kriteria | Bukti di video |
|---|---|
| CDS nyata via SDK | Email Amazon SES masuk ke Gmail (1:10, 2:05) |
| Agentik, mengambil tindakan | Timeline tool: `get_order`, `search_policy`, approval, `execute_refund`, `escalate_to_human` |
| Guardrail + human-in-the-loop | Refund Rp349.000 > batas Rp100.000 → approval di `/approvals`; guard di kode tool |
| Observability | Timeline agen per kasus, sumber dokumen kebijakan, status pengiriman pesan |
| Jalan di AWS | URL CloudFront, AgentCore Runtime, Bedrock KB |
| Kejujuran | Sebut "simulated" untuk pembayaran/kurir dan Simulator untuk inbound |

Jangan katakan WhatsApp/SMS sudah berjalan.

## 4. Checklist submission tersisa

| Item | Status |
|---|---|
| Repo publik + lisensi open source (`LICENSE`, MIT) | Sudah |
| Diagram arsitektur (`docs/architecture.md`) | Sudah |
| README Inggris + instruksi setup | Sudah (cek ulang bagian "Real AWS messaging" + catatan simulated) |
| Deskripsi proyek (masalah, solusi, arsitektur, dampak, yang dibangun saat hackathon) | Belum |
| Video demo ~3 menit (naskah ini) | Belum direkam |
| Tautan solusi: `https://dhv2ziygcntil.cloudfront.net` + instruksi mencoba | Sudah deploy; instruksi akses juri belum final |
| **ACE Opportunity ID** dengan kode kampanye "AWS CDS Agentic AI Hackathon -Sept. 2026" | **BELUM — harus dibuat user di AWS Partner Central** |
| Screenshot email SES di inbox → `docs/evidence/` | Belum (user) |
| Cek tidak ada secret/PII di riwayat git, `.env` tidak ter-commit | Belum diverifikasi |
| Penjelasan WhatsApp (kategori WhatsApp) | Tidak berlaku — WhatsApp belum aktif, jangan daftar kategori ini |
| Submit paling lambat Rabu 28 Okt 22.00 WITA | Belum |
| Setelah submit: pantau biaya | Belum |
