# ResolveAI Dashboard

Konsol supervisor (Next.js App Router, static export) untuk memantau kasus, linimasa agen, approval refund, dan Simulator pesan masuk.

## Menjalankan

```bash
cp .env.example .env.local   # isi NEXT_PUBLIC_API_BASE_URL dan NEXT_PUBLIC_API_KEY
npm install
npm run dev                  # http://localhost:3000
npm run build                # hasil static di out/ (untuk S3 + CloudFront)
npm run lint && npm run typecheck
```

Halaman: `/` overview · `/cases/` daftar · `/case/?id=CASE-…` detail (query param, tanpa rute dinamis) · `/approvals/` · `/simulator/`.
Data di-poll tiap 3 detik (SWR, berhenti saat tab tidak aktif).

## Batasan yang diketahui

- **API key terlihat di bundle.** Semua variabel `NEXT_PUBLIC_*` ditanam ke JavaScript saat build, jadi `NEXT_PUBLIC_API_KEY` bisa dibaca siapa pun yang membuka dashboard. Ini hanya untuk demo hackathon; jangan pakai pola ini di produksi (ganti dengan auth pengguna, mis. Cognito).
- Tanpa login; `decided_by` diisi dari `NEXT_PUBLIC_STAFF_NAME`.
- Pembayaran dan kurir **disimulasikan**; UI menandainya dengan label "simulated" / "Pembayaran disimulasikan".
- Tipe API di `src/lib/api-types.ts` adalah alias dari `src/lib/api-types.gen.ts` (hasil `openapi-typescript` dari `openapi.json`). Regenerasi setelah backend berubah: `npm run gen:types` (butuh `.venv` di root repo).
- Nomor telepon dan email dimask di UI (`src/lib/mask.ts`). Hanya data sintetis.
