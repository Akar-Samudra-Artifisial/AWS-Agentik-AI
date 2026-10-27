# ResolveAI Architecture

Single region (`us-east-1`), single environment (`dev`). All resources are named `resolveai-dev-*` and defined with AWS CDK (Python) in `infra/`, except the manual steps listed in the [README](../README.md#2-manual-aws-steps-not-automated-by-cdk) (model access, SES identity, WABA, SMS origination, Knowledge Base, SSM parameters, AgentCore deployment).

> Status: the architecture is implemented and tested offline; it has **not yet been deployed or verified on AWS**. See [`STATUS.md`](STATUS.md).

## 1. Inbound path (customer → agent → real messages)

```mermaid
flowchart LR
  C([Customer<br/>WhatsApp]) -- message --> EUMS[AWS End User Messaging Social<br/>WABA phone number]
  EUMS -- event destination --> SNS[(SNS topic<br/>inbound-whatsapp)]
  SNS --> D[Lambda dispatcher<br/>dedupe · normalize · upsert customer<br/>find/open case · store message · lock]
  D -- InvokeAgentRuntime --> AR[Bedrock AgentCore Runtime<br/>Strands agent + guards]
  D -. fail-safe .-> FS[mark error · apology · escalate]

  AR --> LLM[Amazon Bedrock<br/>LLM]
  AR -- "11 tools (boto3)" --> T{{Tools}}
  T -- get_order / update_case /<br/>create_voucher / schedule_redelivery /<br/>request_refund / execute_refund /<br/>escalate_to_human --> DDB[(DynamoDB<br/>customers · orders · cases · messages<br/>agent_events · approvals · processed_events)]
  T -- search_policy --> KB[Bedrock Knowledge Base<br/>Titan Embeddings V2<br/>docs in S3 kb-docs]
  T -- send_message /<br/>send_resolution_notice --> MSG[Messaging adapter<br/>fallback WhatsApp → SMS → email]
  MSG --> WA[EUM Social<br/>SendWhatsAppMessage]
  MSG --> SMS[EUM SMS<br/>SendTextMessage]
  MSG --> SES[Amazon SES<br/>SendEmail]
  WA --> C
  SMS --> C
  SES --> C

  SSM[(SSM Parameter Store<br/>/resolveai/dev/...)] -.config.-> D
  SSM -.config.-> AR
```

Notes:
- Every tool call and result is written to `agent_events`, which drives the timeline in the dashboard.
- Tools never take a recipient: `send_message` and `send_resolution_notice` resolve the recipient from the case's customer.
- Payment (`execute_refund`) and courier (`schedule_redelivery`) only update DynamoDB and are labelled **simulated**; the outgoing messages are real.

## 2. Dashboard path (supervisor → API → approval → agent)

```mermaid
flowchart LR
  S([Supervisor]) --> CF[Amazon CloudFront]
  CF -- Origin Access Control --> S3[(S3 web bucket<br/>Next.js static export)]
  S -- "browser fetch (x-api-key), polling 3 s" --> APIGW[API Gateway<br/>HTTP API]
  APIGW --> API[Lambda api<br/>FastAPI + Mangum]
  API <--> DDB[(DynamoDB)]
  API -- "POST /api/approvals/{id}/decision<br/>records approved/rejected" --> DDB
  API -- "async invoke<br/>(approval_decided)" --> D[Lambda dispatcher]
  API -- "POST /api/simulate/inbound<br/>async invoke" --> D
  D --> AR[AgentCore Runtime<br/>agent]
  AR -- execute_refund checks<br/>approval status = approved --> DDB
  AR --> MSG[WhatsApp / SMS / SES]
```

API routes (`backend/api/app.py`): `GET /api/health` (no key), `GET /api/cases`, `GET /api/cases/{case_id}`, `GET /api/approvals`, `POST /api/approvals/{approval_id}/decision`, `POST /api/simulate/inbound`, `GET /api/metrics`. `POST /api/demo/reset` is being added.

## 3. Scenario B: lost parcel, refund above the limit needs approval

```mermaid
sequenceDiagram
  autonumber
  actor R as Customer (WhatsApp)
  participant E as EUM Social + SNS
  participant D as Lambda dispatcher
  participant A as AgentCore agent
  participant DB as DynamoDB
  participant M as WhatsApp / SES
  actor S as Supervisor (dashboard)
  participant API as Lambda api

  R->>E: "ORD-1002 still hasn't arrived after a week"
  E->>D: SNS event
  D->>DB: dedupe, open case, store inbound, lock
  D->>A: invoke (customer_message)
  A->>DB: get_order → no scan ≥ 5 days, Rp349,000
  A->>A: search_policy → refund or reship
  A->>M: send_message (options)
  M-->>R: options
  R->>E: "refund"
  E->>D: SNS event
  D->>A: invoke (customer_message)
  A->>DB: request_refund → amount > Rp100,000<br/>approval APR-… status=pending, case=awaiting_approval
  A->>M: send_message ("being verified by our team")
  M-->>R: under review
  S->>API: POST /api/approvals/{id}/decision (approve)
  API->>DB: approval status=approved, decided_by
  API->>D: async invoke (approval_decided)
  D->>A: invoke (approval_decided)
  A->>DB: execute_refund — guard: approval approved<br/>and matches case + order + amount (SIMULATED payment)
  A->>M: send_resolution_notice (WhatsApp + email)
  M-->>R: refund confirmation
  A->>DB: update_case → resolved (approved_by_staff)
  Note over A,DB: On reject: apology + escalate_to_human, case escalated
```

## 4. Component → file map

| Component | AWS resource | Code in this repo |
|---|---|---|
| Data tables + buckets | DynamoDB (7 tables), S3 `kb-docs` | `infra/stacks/data_stack.py` |
| Inbound topic | SNS `inbound-whatsapp` | `infra/stacks/messaging_stack.py` |
| Knowledge Base | Bedrock KB (created manually), S3 data source | `infra/stacks/knowledge_stack.py`, `rag/policies/*.md`, `rag/eval/queries.yaml` |
| Dashboard hosting | S3 `web` + CloudFront (OAC) | `infra/stacks/web_stack.py`, `dashboard/` |
| Lambdas + API | Lambda `dispatcher`, Lambda `api`, API Gateway HTTP API, IAM | `infra/stacks/compute_stack.py`, `infra/app.py` |
| Dispatcher | Lambda `dispatcher` | `backend/dispatcher/handler.py`, `core.py`, `inbound.py` |
| API | Lambda `api` | `backend/api/app.py`, `schemas.py`, `metrics.py`, `handler.py` |
| Backend services | — | `backend/services/` (`agent_client.py`, `config.py`, `data.py`, `trigger.py`) |
| Agent entrypoint | AgentCore Runtime | `agent/app.py` (fallback Lambda: `agent/lambda_handler.py`) |
| Agent turn + model | Bedrock | `agent/runner.py`, `agent/agent_factory.py`, `agent/prompts/system_id.md` |
| Guards | — | `agent/guards.py`, `agent/tools/registry.py` |
| Tools (11) | DynamoDB, KB, messaging | `agent/tools/orders.py`, `policy_search.py`, `actions.py`, `case.py`, `messaging.py` |
| Shared library | — | `packages/common/src/resolveai_common/` (`models.py`, `repository.py`, `policy.py`, `phone.py`, `logging.py`) |
| Messaging adapters | EUM Social, EUM SMS, SES | `packages/common/src/resolveai_common/messaging/` (`whatsapp.py`, `sms.py`, `ses.py`, `dispatch.py`, `templates/`) |
| Configuration | SSM `/resolveai/dev/...` | `agent/config.py`, `backend/services/config.py` |
| Build / ops scripts | — | `scripts/build_lambda.sh`, `scripts/build_agent.sh`, `scripts/seed.py`, `scripts/send_test_message.py`, `scripts/dump_openapi.py`, `Makefile` |
