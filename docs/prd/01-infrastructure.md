# PRD 01 — Infrastructure (AWS CDK)

Prefix requirement: `INF` · Milestone: M0 (dasar), M4 (compute), M5 (web), M6 (observability)
Prasyarat baca: `00-overview.md` §8, §10, §15.

## 1. Tujuan

Semua resource AWS dapat dibuat dan dihancurkan dengan satu perintah, kecuali langkah manual yang tidak layak diotomasi (§4).

## 2. Keputusan

- IaC: **AWS CDK v2 (Python)**, satu app, beberapa stack, folder `infra/`.
- Region tunggal `us-east-1`. **Di M0, sebelum membuat apa pun**, verifikasi bahwa Bedrock (model yang dipilih), AgentCore, End User Messaging Social, dan Knowledge Bases tersedia di region yang sama. Jika tidak, pilih region lain dan catat di `STATUS.md`.
- Satu environment: `dev`. Nama resource `resolveai-dev-*`. Removal policy `DESTROY`. Tag `project=resolveai`, `env=dev`.
- Agen dideploy lewat **CLI starter toolkit AgentCore** (bukan CDK) agar cepat; ARN runtime disimpan ke SSM.

## 3. Stack dan requirement

| ID | Requirement | Prio |
|---|---|---|
| INF-001 | **DataStack**: tabel DynamoDB sesuai `00-overview.md` §10 (`customers`, `orders`, `cases`, `messages`, `agent_events`, `approvals`, `processed_events`), billing PAY_PER_REQUEST, semua GSI, TTL pada `processed_events.ttl` | P0 |
| INF-002 | **DataStack**: bucket S3 privat `kb-docs` (dokumen kebijakan) dan `web` (dashboard), block public access, enkripsi default | P0 |
| INF-003 | **MessagingStack**: SNS topic `inbound-whatsapp`; topic policy yang mengizinkan service End User Messaging Social mem-publish (sesuai dokumentasi AWS) | P0 |
| INF-004 | **ComputeStack**: Lambda `dispatcher` (Python 3.12, 512 MB, timeout 180 s), subscribe ke SNS inbound, env dari SSM/konfigurasi | P0 |
| INF-005 | **ComputeStack**: Lambda `api` (FastAPI + Mangum, 512 MB, timeout 25 s) di belakang API Gateway HTTP API; CORS hanya untuk origin CloudFront dan `http://localhost:3000` | P0 |
| INF-006 | **IAM** least privilege per principal (§6) | P0 |
| INF-007 | **SSM** parameter sesuai §5; `api/key` bertipe SecureString (atau secret di Secrets Manager) | P0 |
| INF-008 | **KnowledgeStack**: Knowledge Base + data source S3 + vector store; jika L1 CDK memakan >45 menit, buat manual lewat console dan simpan `kb/id` ke SSM (lihat `04-rag.md`) | P0 |
| INF-009 | **WebStack**: CloudFront + S3 `web` dengan Origin Access Control, default root `index.html`; script `scripts/deploy_dashboard.sh` (build → sync S3 → invalidate) | P0 |
| INF-010 | **ObservabilityStack**: dashboard CloudWatch (error Lambda, durasi dispatcher, jumlah pesan terkirim per kanal) dan alarm error | P1 |
| INF-011 | AWS Budget dengan alert email (nilai bisa dikonfigurasi) | P1 |
| INF-012 | Bedrock Guardrails (filter PII dan prompt attack) terpasang ke model agen | P2 |

Packaging Lambda: bundel `backend/` + `packages/common/` + dependency ke satu asset (script `scripts/build_lambda.sh` atau bundling CDK).

## 4. Langkah manual (tidak lewat CDK)

Kerjakan sedini mungkin karena ada proses persetujuan pihak ketiga.

| # | Langkah | Kapan | Catatan |
|---|---|---|---|
| 1 | Aktifkan akses model Bedrock yang dipakai agen dan model embedding (Titan Text Embeddings V2) | M0 | Catat model ID/inference profile ID di SSM `bedrock/model_id` |
| 2 | Verifikasi identitas SES (email pengirim) dan email penerima demo | M0 | Akun SES sandbox: hanya alamat terverifikasi yang bisa menerima |
| 3 | Daftarkan WABA lewat End User Messaging Social (hubungkan akun Meta Business), tambahkan nomor, atur event destination ke SNS `inbound-whatsapp` | **M0, mulai segera** | Proses terlama; tambahkan nomor demo sebagai penerima uji |
| 4 | SMS: siapkan origination identity dan verifikasi nomor tujuan di sandbox | M0–M1 | Cek aturan registrasi sender ID untuk Indonesia di console |
| 5 | `cdk bootstrap` | M0 | |
| 6 | Deploy agen: `scripts/build_agent.sh` lalu `agentcore configure` dan `agentcore launch` | M3 | Simpan runtime ARN ke SSM `agent/runtime_arn` |

## 5. Parameter SSM (`/resolveai/dev/…`)

| Nama | Isi |
|---|---|
| `bedrock/model_id` | Model ID/inference profile LLM agen (dikonfirmasi dari katalog Bedrock di console) |
| `kb/id` | ID Knowledge Base |
| `wa/phone_number_id` | `phone-number-id-…` dari End User Messaging Social |
| `wa/meta_api_version` | mis. `v20.0` (sesuai dokumentasi AWS) |
| `sms/origination_identity` | Nomor/sender ID/pool untuk SMS |
| `ses/from_email` | Email pengirim terverifikasi |
| `agent/runtime_arn` | ARN AgentCore Runtime |
| `api/key` | Shared key demo (SecureString) |
| `demo/phone_e164`, `demo/email` | Kontak developer untuk seed |
| `policy/*` | Opsional, override konstanta kebijakan |

## 6. IAM

| Principal | Izin |
|---|---|
| Role runtime agen | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, `bedrock:Retrieve` (KB), DynamoDB CRUD pada tabel proyek, `ses:SendEmail` (dibatasi ke identity pengirim), `sms-voice:SendTextMessage`, `social-messaging:SendWhatsAppMessage`, `ssm:GetParameter(s)` pada prefix proyek, CloudWatch Logs |
| Lambda `dispatcher` | DynamoDB CRUD, `bedrock-agentcore:InvokeAgentRuntime` pada ARN agen, SSM read, Logs |
| Lambda `api` | DynamoDB CRUD, `lambda:InvokeFunction` ke `dispatcher` (async), SSM read, Logs |
| End User Messaging Social | Publish ke SNS inbound (topic policy) |

Nama action IAM di atas ditulis dari ingatan: **verifikasi** terhadap dokumentasi saat membuat policy, dan perketat `Resource` setelah ARN diketahui.

## 7. Perintah

`make bootstrap` · `make deploy` (urutan: Data → Messaging → Knowledge → Compute → Web) · `make destroy` · `make deploy-agent` · `make deploy-dashboard`

Output CDK: URL API, domain CloudFront, nama tabel, ARN topic SNS.

## 8. Acceptance criteria

- [ ] `make deploy` dari akun bersih berhasil tanpa edit manual (selain §4).
- [ ] Semua tabel dan GSI ada; seed mengisi data.
- [ ] `GET /api/health` lewat API Gateway mengembalikan 200.
- [ ] Lambda `dispatcher` dapat dipicu dari SNS (uji dengan publish manual).
- [ ] Tidak ada bucket publik; tidak ada secret di template/repo.
- [ ] `make destroy` menghapus resource proyek (kecuali yang manual).
