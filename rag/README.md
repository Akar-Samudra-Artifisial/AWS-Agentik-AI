# RAG — Knowledge Base kebijakan

Dokumen kebijakan toko (bahasa Indonesia) sebagai sumber kebenaran yang dapat ditelusuri oleh agen.

## Struktur

```
rag/
  policies/        # 7 dokumen kebijakan (.md) dengan front matter YAML
  eval/
    queries.yaml   # set evaluasi retrieval (hit@4)
```

## Dokumen kebijakan (`policies/`)

| File | Isi |
|---|---|
| `shipping-delay-policy.md` | Ambang keterlambatan, opsi kompensasi, aturan voucher |
| `lost-package-policy.md` | Definisi hilang, refund vs kirim ulang, proses |
| `refund-policy.md` | Batas otomatis, persetujuan staf, waktu pencairan |
| `escalation-policy.md` | Pemicu eskalasi, prioritas, jam staf |
| `address-change-policy.md` | Aturan perubahan alamat per status |
| `communication-guidelines.md` | Nada, contoh frasa, hal yang tidak boleh dijanjikan |
| `faq-courier.md` | Istilah tracking, arti status, estimasi umum |

Setiap dokumen memiliki front matter YAML (`doc_type`, `version`, `updated`). Angka kebijakan **harus** konsisten dengan `packages/common/src/resolveai_common/policy.py`.

## Evaluasi (`eval/`)

`queries.yaml` berisi daftar `{question, expected_source}` untuk mengukur akurasi retrieval.

## Catatan

Skrip ingest (`scripts/ingest_kb.py`) dan evaluasi (`scripts/eval_rag.py`) menyusul pada tahap integrasi AWS (lihat `docs/prd/04-rag.md` RAG-004 dan RAG-007).
