# PRD 06 — Dashboard (Next.js)

Prefix requirement: `DB` · Milestone: M5
Prasyarat baca: `00-overview.md` §6–7, §10; `02-backend.md` §5–6.

## 1. Tujuan

Antarmuka untuk supervisor dan juri: melihat kasus masuk secara langsung, memahami apa yang dilakukan agen langkah demi langkah, menyetujui/menolak aksi sensitif, memicu skenario lewat Simulator, dan membaca metrik dampak. Harus **terbaca jelas di rekaman layar** untuk demo.

## 2. Keputusan teknis

- Next.js (App Router) + TypeScript strict + Tailwind + (opsional) shadcn/ui + SWR + Recharts.
- **Static export** (`output: "export"`) di S3 + CloudFront. Karena itu **tidak memakai rute dinamis** `/cases/[id]`; gunakan `/case?id=CASE-…` dan baca `useSearchParams()` di sisi klien.
- Data via REST (`02-backend.md` §5), polling **3 detik** dengan SWR `refreshInterval`; jeda saat tab tidak aktif.
- Tipe API dihasilkan dari OpenAPI (`openapi-typescript`) ke `dashboard/src/lib/api-types.ts`.
- Konfigurasi build: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_API_KEY` (shared key demo; **batasan yang diketahui**: key terlihat di bundle, hanya untuk demo, catat di README).
- Tanpa login. Satu tema terang yang bersih; kontras baik; font besar untuk rekaman.

## 3. Halaman

| Rute | Isi |
|---|---|
| `/` Overview | KPI cards, grafik, antrean approval ringkas, kasus terbaru, indikator "Live" |
| `/cases` | Tabel kasus dengan filter status dan kanal, pencarian ID/nama |
| `/case?id=` | Detail kasus (§4) |
| `/approvals` | Antrean approval (pending di atas, riwayat di bawah) |
| `/simulator` | Konsol uji untuk memicu pesan masuk |

## 4. Requirement

| ID | Requirement | Prio |
|---|---|---|
| DB-001 | Layout aplikasi: sidebar/topbar, navigasi 5 halaman, indikator koneksi API ("Live"/"Offline") | P0 |
| DB-002 | **Overview**: kartu KPI — Total kasus, Auto-resolved %, Median waktu respons pertama, Eskalasi, Approval pending, Kasus aktif (dari `/metrics`) | P0 |
| DB-003 | **Overview**: grafik batang kasus per kanal dan per kategori; daftar 8 kasus terbaru; panel approval pending dengan tombol aksi cepat | P0 |
| DB-004 | **Daftar kasus**: tabel (ID, pelanggan, kategori, kanal sebagai badge, status sebagai badge, prioritas, ringkasan, waktu relatif), filter status/kanal, klik → detail | P0 |
| DB-005 | **Detail kasus — percakapan**: gelembung chat urut waktu, badge kanal per pesan, penanda penulis (pelanggan/agen/staf/sistem), status pengiriman (ikon sent/delivered/read/failed), label "simulated" bila relevan | P0 |
| DB-006 | **Detail kasus — linimasa agen**: daftar langkah dari `events` (nama tool, ringkasan input, hasil, latensi, ok/gagal), bisa dibuka untuk melihat JSON; hasil `search_policy` menampilkan **nama dokumen sumber** | P0 |
| DB-007 | **Detail kasus — panel samping**: kartu pelanggan (nomor/email dimask), kartu pesanan (status, ETA, `days_late`, nilai), metadata kasus (status, kategori, prioritas, waktu respons pertama, durasi) | P0 |
| DB-008 | **Approval**: kartu dengan kasus, nominal, alasan, ringkasan percakapan; tombol **Approve** dan **Reject** (dengan catatan opsional dan konfirmasi), kondisi loading, hasil 202 ditampilkan, status ter-refresh otomatis, tangani 409 | P0 |
| DB-009 | **Simulator**: pilih pelanggan demo, pilih kanal, textarea pesan, tombol kirim; **3 preset** skenario A/B/C dengan teks siap pakai; setelah kirim, tampilkan tautan ke kasus yang terbentuk (poll sampai kasus muncul) | P0 |
| DB-010 | Status kosong, loading (skeleton), dan error yang informatif di setiap halaman | P0 |
| DB-011 | Auto-scroll percakapan ke pesan terbaru; sorot langkah agen baru | P1 |
| DB-012 | Tombol "Reset demo" (memanggil `/demo/reset`, dengan konfirmasi) | P1 |
| DB-013 | Mode presentasi: ukuran font lebih besar, sembunyikan elemen teknis sekunder | P1 |
| DB-014 | Balasan manual staf dari detail kasus | P2 |
| DB-015 | Penanda audio/notifikasi saat ada approval baru | P2 |

## 5. Desain dan UX

- Warna kanal: WhatsApp hijau, SMS biru, Email abu-abu/ungu; status: hijau (resolved), kuning (awaiting_*), merah (escalated/error), biru (investigating).
- Hirarki visual: KPI di atas, approval pending menonjol (aksen), konten detail di bawah.
- Mobile-friendly dasar (layout tidak rusak di layar sempit), prioritas utama desktop untuk demo.
- Aksesibilitas dasar: label tombol, fokus terlihat, kontras AA, jangan mengandalkan warna saja.
- Teks UI: Bahasa Indonesia; istilah teknis (tool, KB) tetap Inggris.
- Jujur soal simulasi: label kecil "Pembayaran disimulasikan" pada kartu refund/resolusi.

## 6. Struktur kode

```
dashboard/
├─ src/app/{page.tsx, cases/page.tsx, case/page.tsx, approvals/page.tsx, simulator/page.tsx}
├─ src/components/{KpiCard, StatusBadge, ChannelBadge, ChatThread, AgentTimeline, ApprovalCard, OrderCard, CaseTable}
├─ src/lib/{api.ts, api-types.ts, format.ts, mask.ts}
└─ next.config.mjs (output: "export", trailingSlash: true)
```

## 7. Pengujian

- Komponen kunci (ChatThread, AgentTimeline, ApprovalCard) dengan data fixture dari API.
- Uji manual lewat daftar periksa §8 menggunakan data seed.
- Opsional: satu tes e2e Playwright untuk alur Simulator → kasus muncul → approve.

## 8. Acceptance criteria

- [ ] Skenario A, B, C dapat dijalankan penuh dari Simulator dan dipantau di dashboard tanpa refresh manual.
- [ ] Linimasa agen menampilkan tool call beserta sumber kebijakan.
- [ ] Approve/Reject memicu penyelesaian kasus dan UI ter-update ≤5 detik.
- [ ] Nomor telepon dan email dimask di UI.
- [ ] Build static export berhasil dan jalan dari CloudFront; reload langsung di `/case?id=…` berfungsi.
- [ ] Tidak ada error konsol pada alur utama; UI layak direkam pada 1080p.
