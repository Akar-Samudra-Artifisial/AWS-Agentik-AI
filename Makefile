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
	$(CDK) deploy --all --require-approval never

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
