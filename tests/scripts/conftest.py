"""Put ``scripts/`` on ``sys.path`` so the operational scripts import as modules."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
