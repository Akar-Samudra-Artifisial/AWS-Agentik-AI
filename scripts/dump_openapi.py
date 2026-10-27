"""Dump the API OpenAPI document (BE-016) for dashboard type generation.

Usage (from the repo root): ``python scripts/dump_openapi.py [--out dashboard/openapi.json]``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "dashboard" / "openapi.json"))
    args = parser.parse_args()

    from api.app import create_app

    document = create_app().openapi()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
