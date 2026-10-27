# Demo Video Script — ResolveAI (≤ 3:00)

Submission: **AWS CDS Agentic AI Hackathon - Sept. 2026**. Video target 2:55, maksimum 3:00.

Fakta yang boleh diklaim di video:
- CDS nyata: **Amazon SES (email)** via AWS SDK. WhatsApp (EUM Social) dan SMS **tidak** ditampilkan sebagai berjalan — adapter ada, tetapi WABA belum aktif dan SMS belum diuji.
- Inbound pelanggan disimulasikan lewat halaman `/simulator` (kanal `email`); balasan agen terkirim sebagai email SES sungguhan.
- Agen: Strands Agents di Amazon Bedrock AgentCore Runtime (Claude Sonnet 4.5), RAG via Bedrock Knowledge Base (Titan Embeddings V2 + S3 Vectors, eval hit@4 93,8%).
- Guard refund ada di kode tool (`execute_refund` hanya jalan bila approval `approved` di DynamoDB), bukan di prompt.
- Pembayaran dan kurir **simulated** — katakan dengan jujur.
- UI dashboard berbahasa Inggris. Pelanggan demo berbahasa Indonesia dan agen membalas dalam bahasa pelanggan — narator boleh menyebut: "The customer writes in Indonesian; the agent replies in the customer's language."

## 1. Timeline

| Waktu | Di layar | Narasi (EN) | Aksi klik |
|---|---|---|---|
| 0:00–0:15 | Judul + dashboard `/` (metrik) | "Customer-service teams answer the same complaints every day — late parcels, lost packages, refunds. Scripted chatbots reply, but they don't resolve. ResolveAI is an agentic recovery agent that actually takes action." | Buka **Overview** (`/`), diam di kartu metrik |
| 0:15–0:30 | Diagram `docs/architecture.md` | "It runs fully on AWS: API Gateway and Lambda, a Strands agent on Bedrock AgentCore Runtime with Claude Sonnet 4.5, a Bedrock Knowledge Base for policies, DynamoDB for state, and Amazon SES to reach the customer." | Tampilkan diagram (render Mermaid di GitHub) |
| 0:30–0:45 | `/simulator`, kanal `email`, preset A | "For this demo, inbound messages come from our simulator on the email channel. Payments and the courier are simulated; the emails are real." | **Channel** = `Email` → di **Scenario presets** klik **A · Delivery 2 days late** → **Step 1:** ("Pesanan ORD-1001 saya terlambat 2 hari.") → **Send message** |
| 0:45–1:10 | `/case/?id=…` kasus A: timeline agen | "The agent looks up the order, sees it is two days late, and searches the policy knowledge base — here is the source document it cited. It apologises and offers options." | Buka kasus baru dari **Cases** (`/cases/`); sorot "Look up order & tracking" (`get_order`) → "Search company policy (RAG)" (`search_policy`) + **Policy sources:** |
| 1:10–1:25 | Tab Gmail inbox demo | "And this is the real email delivered by Amazon SES, seconds later." | Pindah ke Gmail, buka email terbaru |
| 1:25–1:35 | `/simulator` preset A langkah 2 → kasus A | "The customer picks option 1, and the case is resolved automatically." | Klik **Step 2:** ("1") → **Send message**; tunjukkan badge status berubah ke **Resolved** |
| 1:35–1:55 | `/simulator` preset B → kasus B | "Scenario B: a lost parcel worth 349,000 rupiah. The customer asks for a refund. Our auto-refund limit is 100,000, so the agent cannot pay it out — it requests approval instead." | Preset **B · Lost package, large refund**, **Step 1:** → **Send message**, tunggu balasan, **Step 2:** ("Saya pilih refund saja.") → **Send message**; buka kasus, sorot status **Awaiting approval** + badge **Pending** |
| 1:55–2:15 | `/approvals/` → Approve → kasus B + Gmail | "This guardrail lives in the tool code, not in the prompt: execute_refund only runs when an approval is marked approved in DynamoDB. A staff member approves, the simulated refund executes, and the customer gets a resolution email." | Di **Approvals** klik **✓ Approve** → **Yes, approve**; tunjukkan `execute_refund` di timeline + email resolusi di Gmail |
| 2:15–2:20 | (overlay teks) | "If staff reject, the refund is never executed and the case is escalated." | Tidak ada klik (opsional potong singkat take reject) |
| 2:20–2:40 | `/simulator` preset C → kasus C | "Scenario C: the courier says delivered, the customer says nothing arrived and threatens to call the police. The agent knows its limits — it escalates to a human with high priority." | Preset **C · Marked delivered, never received**, **Step 1:** → **Send message**; buka kasus, sorot "Escalate to a human agent" (`escalate_to_human`), status **Escalated** + badge **High priority** |
| 2:40–2:55 | `/` metrik + `/cases/` | "Every step is observable: tool timeline, cited policy sources, approvals and delivery status per message. ResolveAI fits e-commerce, logistics and telco support. Thank you." | Kembali ke **Overview** (`/`), scroll metrik |

Total: **2:55** (buffer 5 detik).

## 2. Persiapan sebelum rekam

1. Buka `https://dhv2ziygcntil.cloudfront.net/simulator/` → klik tombol **Reset demo** (kartu "Reset demo") → OK pada dialog konfirmasi (hapus kasus non-seed, ORD-1001..1003 kembali ke kondisi seed). Ulangi sebelum tiap take.
2. Pastikan **Channel** di Simulator = `Email` dan kontak pelanggan demo terisi (dari env, jangan tampilkan alamat penuh di layar).
3. Pemanasan: kirim satu pesan uji lalu Reset lagi agar runtime AgentCore tidak cold start saat rekam.
4. Urutan tab browser:
   1. Dashboard **Overview** (`/`)
   2. **Simulator** (`/simulator/`)
   3. **Cases** (`/cases/`) (buka kasus dari sini)
   4. **Approvals** (`/approvals/`)
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
| README Inggris + instruksi setup | Sudah (status kanal jujur, Live demo, Evidence, Submission) |
| Deskripsi proyek (masalah, solusi, arsitektur, dampak) | Sudah (`README.md`) |
| Bukti (case JSON, screenshot dashboard, eval RAG) → `docs/evidence/` | Sudah |
| Video demo ~3 menit (naskah ini) | Selesai — https://www.youtube.com/watch?v=GprVqlJucqU (2:55, Remotion + narasi Amazon Polly; teks narasi final ada di project Remotion `scripts/resolveai/narration.json`) |
| Tautan solusi: `https://dhv2ziygcntil.cloudfront.net` + instruksi mencoba | Sudah (README → Live demo) |
| **ACE Opportunity ID** dengan kode kampanye "AWS CDS Agentic AI Hackathon -Sept. 2026" | **BELUM — harus dibuat user di AWS Partner Central** (README: `TBD`) |
| Screenshot email SES di inbox → `docs/evidence/scenario-{a,b,c}-email.png` | Sudah |
| Cek tidak ada secret/PII di riwayat git, `.env` tidak ter-commit | Sebagian — `git log -p` grep `AKIA…`/`aws_secret_access_key`: 0 match (27 Okt); PII belum dicek |
| Penjelasan WhatsApp (kategori WhatsApp) | Inbound terverifikasi, outbound diblok Meta `131031` — jangan klaim WhatsApp berjalan penuh |
| Submit paling lambat Rabu 28 Okt 22.00 WITA | Belum |
| Setelah submit: pantau biaya | Belum |
