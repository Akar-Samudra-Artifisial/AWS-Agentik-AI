#!/usr/bin/env bash
# Bundle Lambda backend (api + dispatcher) ke build/lambda untuk CDK (context lambda_bundle_path).
#
# Isi bundle: dependency wheel untuk Lambda (Python 3.12, x86_64, manylinux2014) +
# backend/{api,dispatcher,services} + paket resolveai_common (packages/common/src).
# Arsitektur mengikuti default ComputeStack (x86_64); override lewat LAMBDA_PLATFORM.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${LAMBDA_BUILD_DIR:-$ROOT/build/lambda}"
PIP="${PIP:-$ROOT/.venv/bin/pip}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
PLATFORM="${LAMBDA_PLATFORM:-manylinux2014_x86_64}"
PY_VERSION="3.12"

if [[ ! -x "$PIP" ]]; then
  echo "build_lambda: pip tidak ditemukan di $PIP — jalankan 'make install' dulu." >&2
  exit 1
fi

REQ_FILE="$(mktemp)"
trap 'rm -f "$REQ_FILE"' EXIT

# Dependency pihak ketiga: baris non-lokal backend/requirements.txt + dependency
# resolveai_common dari pyproject (paket lokal disalin sebagai source, bukan dibangun).
grep -Ev '^[[:space:]]*(#|$|\./|-e )' "$ROOT/backend/requirements.txt" >"$REQ_FILE"
"$PYTHON" -c '
import sys, tomllib
with open(sys.argv[1], "rb") as fh:
    print("\n".join(tomllib.load(fh)["project"]["dependencies"]))
' "$ROOT/packages/common/pyproject.toml" >>"$REQ_FILE"

rm -rf "$OUT"
mkdir -p "$OUT"

echo "build_lambda: install dependency ($PLATFORM, cp$PY_VERSION) -> $OUT"
"$PIP" install \
  --quiet \
  --disable-pip-version-check \
  --no-compile \
  --requirement "$REQ_FILE" \
  --target "$OUT" \
  --platform "$PLATFORM" \
  --implementation cp \
  --python-version "$PY_VERSION" \
  --only-binary=:all:

echo "build_lambda: salin kode backend + resolveai_common"
for pkg in api dispatcher services; do
  cp -R "$ROOT/backend/$pkg" "$OUT/$pkg"
done
cp -R "$ROOT/packages/common/src/resolveai_common" "$OUT/resolveai_common"

# ComputeStack mengharapkan <name>/handler.py dengan atribut `handler`. Handler api
# didefinisikan di api/app.py (Mangum); tambahkan shim bila backend belum menyediakannya.
if [[ ! -f "$OUT/api/handler.py" ]]; then
  cat >"$OUT/api/handler.py" <<'PY'
"""Lambda entrypoint api (dibuat oleh scripts/build_lambda.sh): re-export handler Mangum."""

from .app import handler

__all__ = ["handler"]
PY
fi

find "$OUT" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "build_lambda: selesai ($(du -sh "$OUT" | cut -f1))"
