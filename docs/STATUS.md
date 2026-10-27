# STATUS

Diperbarui oleh Claude Code setelah tiap milestone.

| Milestone | Status | Catatan |
|---|---|---|
| M0 Fondasi & akses | selesai (AWS) | Akun `bayu-admin` us-east-1, `make bootstrap`/`deploy` (5 stack), `make seed` (5 pelanggan, 8 order, 25 kasus), Bedrock `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, SES identity terverifikasi. |
| M1 Messaging nyata | sebagian | Adapter SES/WhatsApp/SMS + dispatch/fallback + template diuji offline (Stubber). `scripts/send_test_message.py` ada. Belum: kirim nyata, parser inbound WA dari fixture SNS nyata (MSG-008; parser sementara ditulis dari docs). |
| M2 RAG | sebagian | 7 dokumen kebijakan + `rag/eval/queries.yaml` (16 query), `scripts/ingest_kb.py` (`make ingest-kb`), `scripts/eval_rag.py` (`--static` → hit@4 16/16). Belum: Knowledge Base nyata, ingest & eval ke KB. |
| M3 Agent | sebagian | Runtime AgentCore `resolveai_dev_agent-1oIRbq6w06` READY (direct_code_deploy, `scripts/stage_agentcore.sh`), ARN di SSM. Skenario A nyata lulus (Bedrock + 6 tool ok). Belum: eval 14 percakapan, KB nyata (masih policy statis). |
| M4 Backend & orkestrasi | sebagian | API + dispatcher ter-deploy; `/simulate/inbound` → AgentCore → email SES nyata (skenario A). Belum: `make e2e` penuh (B/C), WhatsApp inbound. |
| M5 Dashboard | sebagian | Ter-deploy di CloudFront `https://dhv2ziygcntil.cloudfront.net`, terhubung API nyata (200). Belum: cek visual menyeluruh. |
| M6 Hardening & submission | sebagian | `LICENSE` (MIT), `README.md` (Inggris), `docs/architecture.md` (Mermaid), git repo (remote GitHub `Akar-Samudra-Artifisial/AWS-Agentik-AI`). Belum: video, bukti pesan nyata, ACE Opportunity ID, persempit IAM. |

Verifikasi terakhir (2026-10-27): `.venv/bin/pytest -q tests` → 233 passed, 9 skipped; `tests/agent` → 69 passed; ruff bersih; skenario A nyata di AWS lulus (13 agent_events, email terkirim).

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
- 2026-10-27 · Model `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (inference profile) · `claude-sonnet-5` AccessDenied untuk akun ini.
- 2026-10-27 · `make deploy` membaca context dari env/`.env` (`SES_FROM_EMAIL`, `DEMO_RESET_ENABLED` default true, dst.) · deploy tanpa `-c` menghapus env runtime Lambda.
- 2026-10-27 · Lisensi MIT, `Copyright (c) 2026 Akar Samudra Artifisial` · syarat lisensi open source.

## Blocker
- Belum dikonfirmasi: Titan Embeddings V2 (KB), status WABA, SMS origination identity, ACE Opportunity ID.

## Temuan / utang teknis
- IAM masih longgar: kirim pesan `Resource:*` (`infra/stacks/compute_stack.py:88`), AgentCore `runtime/*` (`:73`) → persempit setelah ARN diketahui.
- Dev lokal Python 3.14; target Lambda 3.12 belum diuji di runtime 3.12.
- Eval & e2e mengirim pesan nyata ke kontak demo (eval 14×3 via email; e2e default WhatsApp) dan bergantung pada `/demo/reset`.
- `/demo/reset` tidak menghapus pelanggan non-seed buatan simulator.
- Role runtime AgentCore (`AmazonBedrockAgentCoreSDKRuntime-us-east-1-ab2870b730`) dibuat toolkit + inline policy `resolveai-dev-agent-runtime` manual, di luar CDK.
- Sort key tabel `messages`/`agent_events` = `ts#msg_id`/`ts#seq` (infra); kode sekarang memakai konstanta di `repository.py` + test regresi mencocokkan `data_stack.py`.

## Bukti pesan nyata (untuk juri)
(ID pesan WhatsApp/SMS/SES + lokasi screenshot)
- 2026-10-27 · SES email · skenario A `CASE-20261027-CFD7` (ORD-1001, late_delivery → awaiting_customer), `delivery_status: sent` + `provider_message_id` SES. Screenshot inbox: belum (`docs/evidence/`).
