# PRD 04 — RAG (Knowledge Base kebijakan)

Prefix requirement: `RAG` · Milestone: M2 (bisa paralel dengan M1/M3)
Prasyarat baca: `00-overview.md` §10 (konstanta kebijakan); `03-agent.md` §5.

## 1. Tujuan

Agen mengambil keputusan berdasarkan kebijakan toko yang dapat ditelusuri ke dokumen sumber, bukan dari ingatan model. Setiap pencarian menghasilkan potongan teks + nama sumber yang ditampilkan di linimasa dashboard.

## 2. Keputusan

- **Amazon Bedrock Knowledge Bases** dengan sumber data S3 (`kb-docs`).
- Embedding: **Amazon Titan Text Embeddings V2** (1024 dimensi).
- Vector store: pilih yang tersedia dan termurah di region terpilih: **S3 Vectors** (utama, jika tersedia untuk KB di region tersebut) → Aurora PostgreSQL/pgvector → OpenSearch Serverless (mahal; hapus setelah hackathon). Verifikasi ketersediaan di M0.
- Retrieval: API `Retrieve` (bukan `RetrieveAndGenerate`); generasi tetap oleh agen.
- Dokumen sedikit dan pendek, jadi chunking sederhana.
- **Fallback statis**: seluruh dokumen kebijakan (kecil) dapat dimuat dari `rag/policies/` ke dalam hasil `search_policy` bila KB gagal atau latensi >5 detik.

## 3. Sumber kebenaran kebijakan

Dokumen bahasa Indonesia, front matter YAML (`doc_type`, `version`, `updated`). Aturan di bawah **harus** muncul konsisten di dokumen dan sama dengan `packages/common/policy.py`.

| Situasi | Aturan |
|---|---|
| Terlambat ≥1 hari | Minta maaf, berikan info tracking terbaru |
| Terlambat ≥2 hari | Tawarkan: (a) jadwal ulang/prioritas pengiriman, (b) voucher maks Rp25.000 (1 per kasus, otomatis), (c) bicara dengan staf |
| Tanpa pembaruan tracking ≥5 hari | Dianggap hilang: pelanggan memilih refund penuh atau kirim ulang |
| Refund ≤Rp100.000 | Otomatis (kebijakan) |
| Refund >Rp100.000 | Wajib persetujuan staf; estimasi verifikasi ≤1 jam kerja |
| Refund dana | Ke metode pembayaran asal, 3–5 hari kerja |
| Status delivered, pelanggan tidak menerima | Eskalasi ke staf untuk investigasi kurir |
| Perubahan alamat | Hanya sebelum status `shipped`; setelahnya eskalasi |
| Ancaman hukum/media, tuduhan penipuan, kata kasar berulang | Eskalasi prioritas tinggi |
| Jam staf | 08.00–20.00 WIB; di luar jam, janji dihubungi pada jam kerja berikutnya |
| Nada | Sopan, empatik, ringkas; tidak menjanjikan di luar kebijakan |

## 4. Dokumen yang harus dibuat (`rag/policies/`)

Masing-masing 150–400 kata, bahasa Indonesia, ditulis natural seperti kebijakan toko sungguhan (bukan sekadar tabel di atas).

| File | Isi |
|---|---|
| `shipping-delay-policy.md` | Ambang keterlambatan, opsi kompensasi, aturan voucher |
| `lost-package-policy.md` | Definisi hilang, refund vs kirim ulang, proses |
| `refund-policy.md` | Batas otomatis, persetujuan staf, waktu pencairan, pengecualian |
| `escalation-policy.md` | Pemicu eskalasi, prioritas, jam staf, apa yang dikatakan ke pelanggan |
| `address-change-policy.md` | Aturan perubahan alamat per status |
| `communication-guidelines.md` | Nada, contoh frasa, hal yang tidak boleh dijanjikan, penanganan pelanggan marah |
| `faq-courier.md` | Istilah tracking, arti status, estimasi umum |

## 5. Requirement

| ID | Requirement | Prio |
|---|---|---|
| RAG-001 | Tulis 7 dokumen kebijakan §4 dengan aturan §3 yang konsisten | P0 |
| RAG-002 | Buat KB, data source S3, embedding Titan V2, vector store (§2); simpan `kb/id` di SSM | P0 |
| RAG-003 | Chunking: fixed-size ≈300 token, overlap 15–20%; metadata `doc_type` dari front matter/nama file | P0 |
| RAG-004 | `scripts/ingest_kb.py`: sync dokumen ke S3, memulai ingestion job, menunggu selesai, melaporkan status | P0 |
| RAG-005 | Tool `search_policy(query)` memanggil `bedrock-agent-runtime.retrieve` (top-k 4), mengembalikan `[{text, source, score}]` | P0 |
| RAG-006 | Fallback statis jika KB error/timeout (>5 detik) | P0 |
| RAG-007 | Set eval `rag/eval/queries.yaml`: ≥12 pertanyaan dengan dokumen sumber yang diharapkan; `scripts/eval_rag.py` menghitung hit@4 | P0 |
| RAG-008 | Tampilkan `source` hasil retrieval di `agent_events` agar terlihat di dashboard | P0 |
| RAG-009 | Filter metadata (`doc_type`) pada query bila relevan | P2 |
| RAG-010 | Reranking atau hybrid search | P2 |

## 6. Set evaluasi (contoh minimal)

| Pertanyaan | Sumber diharapkan |
|---|---|
| Pesanan terlambat 2 hari, kompensasi apa yang boleh? | `shipping-delay-policy` |
| Kapan paket dianggap hilang? | `lost-package-policy` |
| Refund Rp349.000 perlu persetujuan? | `refund-policy` |
| Berapa lama dana kembali? | `refund-policy` |
| Pelanggan mengancam lapor polisi | `escalation-policy` |
| Pelanggan bilang sudah delivered tapi tidak terima | `escalation-policy` |
| Bisa ubah alamat setelah dikirim? | `address-change-policy` |
| Bagaimana menjawab pelanggan yang marah? | `communication-guidelines` |
| Maksimal nilai voucher? | `shipping-delay-policy` |
| Jam operasional staf? | `escalation-policy` |
| Arti status "out for delivery"? | `faq-courier` |
| Boleh menjanjikan refund pasti? | `communication-guidelines` / `refund-policy` |

## 7. Acceptance criteria

- [ ] Ingestion selesai tanpa error; semua 7 dokumen terindeks.
- [ ] hit@4 ≥ 90% pada set eval (≥11 dari 12).
- [ ] `search_policy` mengembalikan hasil dalam ≤3 detik (p90) dan `source` terisi.
- [ ] Mematikan akses KB (simulasi error) tetap menghasilkan jawaban via fallback statis.
- [ ] Angka di dokumen = konstanta di `policy.py` (test sederhana yang memeriksa kemunculan nilai).
