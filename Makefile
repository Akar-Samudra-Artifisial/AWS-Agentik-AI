# ResolveAI — Makefile
# Dev lokal memakai virtualenv di .venv; CDK memakai infra/.venv (lihat infra/cdk.json).
# Target AWS (bootstrap/deploy/destroy/seed) butuh kredensial AWS di environment.

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

INFRA_VENV := infra/.venv
# CLI CDK dijalankan via npx (tanpa install global); `cd infra` agar cdk.json terbaca.
CDK := cd infra && . .venv/bin/activate && npx --yes aws-cdk@2

# Context deploy dari env/.env agar `make deploy` tidak menghapus env runtime Lambda.
-include .env
# Ekspor variabel .env ke script Python (e2e, seed, eval) yang membaca env.
export $(shell [ -f .env ] && sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
DEMO_RESET_ENABLED ?= true
DEPLOY_CONTEXT := -c demo_reset_enabled=$(DEMO_RESET_ENABLED) \
	$(if $(SES_FROM_EMAIL),-c ses_from_email=$(SES_FROM_EMAIL)) \
	$(if $(SMS_ORIGINATION_IDENTITY),-c sms_origination_identity=$(SMS_ORIGINATION_IDENTITY)) \
	$(if $(WA_PHONE_NUMBER_ID),-c wa_phone_number_id=$(WA_PHONE_NUMBER_ID)) \
	$(if $(WA_META_API_VERSION),-c wa_meta_api_version=$(WA_META_API_VERSION))

.PHONY: install infra-install test lint build-lambda build-agent synth bootstrap deploy \
	destroy seed e2e ingest-kb eval-rag eval-agent dashboard-dev clean

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: $(VENV)
	$(PIP) install -e "packages/common[dev]"

$(INFRA_VENV):
	python3 -m venv $(INFRA_VENV)
	$(INFRA_VENV)/bin/pip install --upgrade pip

infra-install: $(INFRA_VENV)
	$(INFRA_VENV)/bin/pip install -r infra/requirements.txt

test:
	$(PYTEST) -q tests

lint:
	$(RUFF) check packages/common/src tests scripts

build-lambda:
	bash scripts/build_lambda.sh

build-agent:
	@if [ -f scripts/build_agent.sh ]; then bash scripts/build_agent.sh; \
	else echo "build-agent: scripts/build_agent.sh belum ada."; exit 1; fi

synth: build-lambda
	$(CDK) synth --quiet

bootstrap:
	$(CDK) bootstrap

deploy: build-lambda
	$(CDK) deploy --all --require-approval never $(DEPLOY_CONTEXT)

destroy:
	$(CDK) destroy --all --force

seed:
	$(PY) scripts/seed.py

# Target AWS di bawah butuh RESOLVEAI_API_URL (output CDK api-url) dan kredensial AWS;
# argumen tambahan lewat ARGS, mis. `make e2e ARGS="--only A"`.
e2e:
	$(PY) scripts/e2e.py --reset $(ARGS)

ingest-kb:
	$(PY) scripts/ingest_kb.py $(ARGS)

eval-rag:
	$(PY) scripts/eval_rag.py --output docs/evidence/eval_rag.md $(ARGS)

eval-agent:
	$(PY) scripts/eval_agent.py --runs 3 --output docs/evidence/eval_agent.md $(ARGS)

dashboard-dev:
	cd dashboard && npm run dev

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
