# CLAUDE.md — ResolveAI

Agen AI untuk pemulihan keluhan pelanggan (WhatsApp/SMS/email) di atas AWS. Dibangun solo untuk hackathon AWS Partners dengan tenggat sangat ketat. **Kecepatan eksekusi > kesempurnaan.**

## Cara bekerja
1. Baca `docs/prd/00-overview.md` sampai habis, lalu PRD platform yang sedang dikerjakan (`01`–`07`).
2. Ikuti urutan milestone M0→M6 di `00-overview.md` §12. Selesaikan exit criteria satu milestone sebelum lanjut, kecuali tugas yang ditandai paralel.
3. Prioritas: **P0** wajib, **P1** jika waktu cukup, **P2** stretch. Jangan mengerjakan P1/P2 sebelum seluruh P0 milestone itu hijau.
4. Setelah tiap milestone: jalankan test, lalu perbarui `docs/STATUS.md` (selesai / sedang jalan / blocker / keputusan).
5. Jika PRD ambigu: pilih opsi paling sederhana yang memenuhi acceptance criteria, catat di STATUS.md → "Keputusan", lalu lanjut. Berhenti dan tanya hanya untuk blocker nyata (kredensial, akses AWS, kuota).
6. Jika satu fitur memakan >60 menit tanpa kemajuan, pakai fallback yang tercantum di PRD terkait dan lanjut.

## Aturan keras (tidak boleh dilanggar)
- Pesan keluar (WhatsApp/SMS/email) **harus** dikirim lewat AWS SDK sungguhan di runtime. Mock hanya boleh ada di folder `tests/`.
- Aksi sensitif (refund di atas batas) **hanya** boleh dieksekusi bila ada approval berstatus `approved` di DynamoDB. Guard ada di kode tool, bukan di prompt.
- Tool agen tidak boleh punya parameter penerima pesan; penerima selalu diturunkan dari kasus.
- Tanpa secret/credential di repo. Konfigurasi lewat SSM Parameter Store/env. `.env` masuk `.gitignore`.
- Hanya data sintetis. Nomor/email demo milik developer diambil dari env, jangan di-hardcode.
- Pembayaran dan kurir **disimulasikan**; sebutkan dengan jujur di README dan UI ("simulated").
- Jangan menambah fitur di luar PRD tanpa mencatatnya di STATUS.md.

## Stack & konvensi
- Python 3.12, boto3, pydantic v2, FastAPI + Mangum, Strands Agents, pytest, ruff. Infra: AWS CDK (Python).
- Dashboard: Next.js (App Router, static export), TypeScript strict, Tailwind, SWR, Recharts.
- Waktu: UTC ISO 8601. Uang: integer rupiah (`*_idr`). ID berprefix: `CUST-`, `ORD-`, `CASE-`, `APR-`.
- Log JSON terstruktur dengan `case_id` sebagai correlation ID; mask nomor telepon (`+62812****789`).
- Type hints wajib. Fungsi tool punya docstring yang jelas (dibaca oleh LLM).
- Commit kecil per tugas, format `area: ringkasan` (mis. `agent: add request_refund guard`).

## Perintah (buat Makefile di M0)
`make install` · `make test` · `make lint` · `make deploy` · `make seed` · `make e2e` · `make dashboard-dev`

## Peta dokumen
`00` overview · `01` infrastructure · `02` backend · `03` agent · `04` rag · `05` messaging · `06` dashboard · `07` testing & demo
