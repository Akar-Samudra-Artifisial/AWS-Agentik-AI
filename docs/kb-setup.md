# Setup Knowledge Base (manual, dapat diulang)

KB dibuat manual lewat AWS CLI (bukan CDK). Region `us-east-1`. Vector store **S3 Vectors**
(bukan OpenSearch Serverless/Aurora — biaya). Embedding **Titan Text Embeddings V2** (1024 dimensi).

Nama resource dev:

| Resource | Nama |
|---|---|
| Vector bucket | `resolveai-dev-kb-vectors` |
| Vector index | `resolveai-dev-kb-index` (float32, 1024, cosine) |
| IAM role KB | `resolveai-dev-kb-role` (inline policy `resolveai-dev-kb-access`) |
| Knowledge Base | `resolveai-dev-kb` |
| Data source | `resolveai-dev-kb-docs` (S3 bucket kb-docs dari DataStack, FIXED_SIZE 300 token, overlap 20%) |
| SSM | `/resolveai/dev/kb/id`, `/resolveai/dev/kb/data_source_id`, `/resolveai/dev/kb/docs_bucket` |

## 0. Variabel

```bash
export AWS_REGION=us-east-1
ACCT=$(aws sts get-caller-identity --query Account --output text)
DOCS_BUCKET=<nama bucket kb-docs dari output DataStack>
INDEX_ARN=arn:aws:s3vectors:$AWS_REGION:$ACCT:bucket/resolveai-dev-kb-vectors/index/resolveai-dev-kb-index
```

## 1. Cek akses model embedding

```bash
aws bedrock-runtime invoke-model --model-id amazon.titan-embed-text-v2:0 \
  --body '{"inputText":"halo","dimensions":1024}' --cli-binary-format raw-in-base64-out /tmp/emb.json
```

`AccessDeniedException` → aktifkan model access Titan Text Embeddings V2 di console Bedrock.

## 2. Vector bucket + index

```bash
aws s3vectors create-vector-bucket --vector-bucket-name resolveai-dev-kb-vectors
aws s3vectors create-index --vector-bucket-name resolveai-dev-kb-vectors \
  --index-name resolveai-dev-kb-index --data-type float32 --dimension 1024 --distance-metric cosine \
  --metadata-configuration '{"nonFilterableMetadataKeys":["AMAZON_BEDROCK_TEXT","AMAZON_BEDROCK_METADATA"]}'
```

## 3. IAM role untuk KB

`trust.json` (trust `bedrock.amazonaws.com`, dibatasi ke akun sendiri):

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"bedrock.amazonaws.com"},
 "Action":"sts:AssumeRole","Condition":{"StringEquals":{"aws:SourceAccount":"<ACCT>"},
 "ArnLike":{"aws:SourceArn":"arn:aws:bedrock:us-east-1:<ACCT>:knowledge-base/*"}}}]}
```

`perm.json` (izin minimum):

```json
{"Version":"2012-10-17","Statement":[
 {"Sid":"Embed","Effect":"Allow","Action":"bedrock:InvokeModel",
  "Resource":"arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"},
 {"Sid":"DocsList","Effect":"Allow","Action":"s3:ListBucket","Resource":"arn:aws:s3:::<DOCS_BUCKET>"},
 {"Sid":"DocsRead","Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::<DOCS_BUCKET>/*"},
 {"Sid":"Vectors","Effect":"Allow",
  "Action":["s3vectors:PutVectors","s3vectors:GetVectors","s3vectors:DeleteVectors","s3vectors:QueryVectors","s3vectors:GetIndex"],
  "Resource":"<INDEX_ARN>"}]}
```

```bash
aws iam create-role --role-name resolveai-dev-kb-role --assume-role-policy-document file://trust.json
aws iam put-role-policy --role-name resolveai-dev-kb-role --policy-name resolveai-dev-kb-access \
  --policy-document file://perm.json
sleep 10  # propagasi IAM
```

Bucket kb-docs memakai SSE-S3 (AES256), jadi tidak perlu izin KMS.

## 4. Knowledge Base + data source

```bash
KB_ID=$(aws bedrock-agent create-knowledge-base --name resolveai-dev-kb \
  --role-arn arn:aws:iam::$ACCT:role/resolveai-dev-kb-role \
  --knowledge-base-configuration '{"type":"VECTOR","vectorKnowledgeBaseConfiguration":{
     "embeddingModelArn":"arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0",
     "embeddingModelConfiguration":{"bedrockEmbeddingModelConfiguration":{"dimensions":1024,"embeddingDataType":"FLOAT32"}}}}' \
  --storage-configuration "{\"type\":\"S3_VECTORS\",\"s3VectorsConfiguration\":{\"indexArn\":\"$INDEX_ARN\"}}" \
  --query knowledgeBase.knowledgeBaseId --output text)
aws bedrock-agent get-knowledge-base --knowledge-base-id $KB_ID --query knowledgeBase.status  # tunggu ACTIVE

DS_ID=$(aws bedrock-agent create-data-source --knowledge-base-id $KB_ID --name resolveai-dev-kb-docs \
  --data-source-configuration "{\"type\":\"S3\",\"s3Configuration\":{\"bucketArn\":\"arn:aws:s3:::$DOCS_BUCKET\"}}" \
  --vector-ingestion-configuration '{"chunkingConfiguration":{"chunkingStrategy":"FIXED_SIZE",
     "fixedSizeChunkingConfiguration":{"maxTokens":300,"overlapPercentage":20}}}' \
  --query dataSource.dataSourceId --output text)
```

Catatan: percobaan pertama `create-knowledge-base` sempat gagal `AccessDeniedException`
(`bedrock:CreateKnowledgeBase`) walau user punya AdministratorAccess; diulang beberapa detik
kemudian berhasil (dugaan: propagasi role baru). Bila terjadi, tunggu lalu ulangi.

## 5. SSM

```bash
aws ssm put-parameter --type String --overwrite --name /resolveai/dev/kb/id --value "$KB_ID"
aws ssm put-parameter --type String --overwrite --name /resolveai/dev/kb/data_source_id --value "$DS_ID"
aws ssm put-parameter --type String --overwrite --name /resolveai/dev/kb/docs_bucket --value "$DOCS_BUCKET"
```

## 6. Izin Retrieve untuk runtime agen

Inline policy `resolveai-dev-agent-runtime` pada role runtime AgentCore harus memuat
`bedrock:Retrieve` pada `arn:aws:bedrock:us-east-1:<ACCT>:knowledge-base/*` (atau ARN KB spesifik).
Cek dulu dengan `aws iam get-role-policy`, pertahankan statement lain bila menambah.

## 7. Ingest + eval

```bash
make ingest-kb   # upload rag/policies/*.md + sidecar metadata, start ingestion job, poll sampai COMPLETE
make eval-rag    # hit@4 via Retrieve, target ≥90%; hasil di docs/evidence/eval_rag.md
```

## Biaya (perkiraan, 7 dokumen ±12 KB)

- S3 Vectors: penyimpanan & query untuk puluhan vektor → < $0,01/bulan.
- Titan Embeddings V2: ±3–5 ribu token per ingest + 1 query embedding per retrieve → di bawah 1 sen.
- Tidak ada biaya tetap per jam (beda dengan OpenSearch Serverless).

## Teardown

```bash
aws bedrock-agent delete-data-source --knowledge-base-id $KB_ID --data-source-id $DS_ID
aws bedrock-agent delete-knowledge-base --knowledge-base-id $KB_ID
aws s3vectors delete-index --vector-bucket-name resolveai-dev-kb-vectors --index-name resolveai-dev-kb-index
aws s3vectors delete-vector-bucket --vector-bucket-name resolveai-dev-kb-vectors
aws iam delete-role-policy --role-name resolveai-dev-kb-role --policy-name resolveai-dev-kb-access
aws iam delete-role --role-name resolveai-dev-kb-role
```
