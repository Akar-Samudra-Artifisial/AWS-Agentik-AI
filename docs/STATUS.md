# STATUS

Diperbarui oleh Claude Code setelah tiap milestone.

| Milestone | Status | Catatan |
|---|---|---|
| M0 Fondasi & akses | sebagian | Repo, `Makefile` (install/test/lint/infra-install/build-lambda/build-agent/synth/bootstrap/deploy/destroy/seed/dashboard-dev), `packages/common` + test, CDK 5 stack (`make synth` lulus), `scripts/seed.py` (moto). Belum: kredensial AWS, `bootstrap`/`deploy`/`seed` nyata, panggilan Bedrock, verifikasi SES. |
| M1 Messaging nyata | sebagian | Adapter SES/WhatsApp/SMS + dispatch/fallback + template diuji offline (Stubber). `scripts/send_test_message.py` ada. Belum: kirim nyata, parser inbound WA dari fixture SNS nyata (MSG-008; parser sementara ditulis dari docs). |
| M2 RAG | sebagian | 7 dokumen kebijakan + `rag/eval/queries.yaml` (16 query), `scripts/ingest_kb.py` (`make ingest-kb`), `scripts/eval_rag.py` (`--static` → hit@4 16/16). Belum: Knowledge Base nyata, ingest & eval ke KB. |
| M3 Agent | sebagian | 11 tool + guard, Strands factory (`agent/agent_factory.py`), `run_turn` (`agent/runner.py`), entrypoint AgentCore (`agent/app.py`) + fallback Lambda (`agent/lambda_handler.py`), diuji offline dengan model palsu (`agent/.venv`: 69 passed). `scripts/eval_agent.py` + `agent/eval/golden.yaml` (14 percakapan, `--validate` OK). Belum: deploy AgentCore, panggilan Bedrock nyata, menjalankan eval. |
| M4 Backend & orkestrasi | sebagian | API FastAPI+Mangum (`backend/api/`) + dispatcher (`backend/dispatcher/`) diuji offline (moto + TestClient), `POST /api/demo/reset` (P1, aktif via `DEMO_RESET_ENABLED`), `scripts/e2e.py` (`make e2e`, A/B-approve/B-reject/C). Belum: deploy & e2e nyata. |
| M5 Dashboard | sebagian | 5 halaman static export, tipe dari OpenAPI (`npm run gen:types`), `npm run build` lulus. Belum: cek visual & sambung ke API nyata. |
| M6 Hardening & submission | sebagian | `LICENSE` (MIT), `README.md` (Inggris), `docs/architecture.md` (Mermaid), git repo (remote GitHub `Akar-Samudra-Artifisial/AWS-Agentik-AI`). Belum: video, bukti pesan nyata, ACE Opportunity ID, persempit IAM. |

Verifikasi terakhir (2026-10-27): `.venv/bin/pytest -q tests` → 232 passed, 9 skipped (test Strands jalan di `agent/.venv`: 69 passed); ruff → bersih; `make synth` → 5 stack; dashboard `tsc --noEmit` → bersih.

## Keputusan
(tanggal · keputusan · alasan)
- 2026-10-27 · Test messaging pakai `botocore.stub.Stubber` + injeksi `client`, bukan AWS nyata · PRD 05 §7 meminta unit test tanpa jaringan; pengiriman nyata diverifikasi manual via `send_test_message.py` di M1/M6.
- 2026-10-27 · `send_test_message.py` dipanggil `python scripts/...` dan diberi executable bit · MSG-010 untuk uji manual + bukti juri.
- 2026-10-27 · Bucket web dipindah dari DataStack ke WebStack · menghindari siklus dependensi antar-stack CDK.
- 2026-10-27 · KB Bedrock & parameter SSM tidak dibuat via CDK · SecureString tidak didukung CloudFormation; KB pakai jalur manual (INF-008).
- 2026-10-27 · Lambda memakai bundle `build/lambda` (`make build-lambda`), fallback `infra/placeholder_lambda` · backend memakai import `services`/`resolveai_common` yang tidak bisa dipakai langsung sebagai asset.
- 2026-10-27 · `execute_refund` menerima `order_id` + `amount_idr` selain `approval_id` · guard harus mencocokkan approval dengan case+order+amount (aturan keras #2).
- 2026-10-27 · `/health` tanpa API key · dipakai untuk smoke test/health check.
- 2026-10-27 · Env tambahan dashboard `NEXT_PUBLIC_DEMO_PHONE_E164` (di luar PRD) · preset Simulator butuh nomor pelanggan demo tanpa hardcode.
- 2026-10-27 · Dashboard menghitung `days_late`/`days_since_last_scan` dari `eta`/`last_scan_at` · backend tidak mengirim field turunan itu.
- 2026-10-27 · Kasus seed tidak punya `order_id` · menghindari referensi ke pesanan yang tidak ada.
- 2026-10-27 · Builder seed dipindah ke `resolveai_common/seed_data.py` · dipakai juga oleh `/demo/reset` di Lambda.
- 2026-10-27 · `/demo/reset` default nonaktif (403) kecuali `DEMO_RESET_ENABLED=true` (CDK `-c demo_reset_enabled=true`) · cegah reset tak sengaja.
- 2026-10-27 · Identitas pengirim (`SES_FROM_EMAIL`, `SMS_ORIGINATION_IDENTITY`, `WA_PHONE_NUMBER_ID`, `WA_META_API_VERSION`) diisi ke env Lambda via CDK context `-c` · adapter messaging membaca env; runtime AgentCore juga perlu env yang sama saat `agentcore launch`.
- 2026-10-27 · `eval_agent.py` lewat API (bukan `run_turn` langsung) + golden di `agent/eval/golden.yaml` · script di luar `tests/` tidak boleh memakai mock pengirim pesan.
- 2026-10-27 · Parameter SSM tambahan `kb/docs_bucket`, `kb/data_source_id` (atau env `KB_DOCS_BUCKET`/`KB_DATA_SOURCE_ID`); URL API via env `RESOLVEAI_API_URL` · tidak ada di PRD 01 §5.
- 2026-10-27 · Lisensi MIT, `Copyright (c) 2026 Akar Samudra Artifisial` · syarat lisensi open source.

## Blocker
- Kredensial AWS belum dikonfigurasi (`aws configure sso`, region `us-east-1`) → deploy, seed, Bedrock, SES nyata tertahan.
- Belum dikonfirmasi: akses model Bedrock + Titan Embeddings V2, SES identity terverifikasi, status WABA, SMS sandbox, ACE Opportunity ID.

## Temuan / utang teknis
- IAM masih longgar: kirim pesan `Resource:*` (`infra/stacks/compute_stack.py:88`), AgentCore `runtime/*` (`:73`) → persempit setelah ARN diketahui.
- Dev lokal Python 3.14; target Lambda 3.12 belum diuji di runtime 3.12.
- Eval & e2e mengirim pesan nyata ke kontak demo (eval 14×3 via email; e2e default WhatsApp) dan bergantung pada `/demo/reset`.
- `/demo/reset` tidak menghapus pelanggan non-seed buatan simulator.

## Bukti pesan nyata (untuk juri)
(ID pesan WhatsApp/SMS/SES + lokasi screenshot)
