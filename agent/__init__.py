"""ResolveAI agent package (Strands Agents on Bedrock AgentCore Runtime).

The deploy bundle vendors ``resolveai_common`` and the policy documents into
``agent/_vendor/`` (``scripts/build_agent.sh``). The vendor dir is appended to
``sys.path`` so an installed ``resolveai_common`` (dev venv) still takes precedence.
"""

import os
import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
if _VENDOR_DIR.is_dir():
    if str(_VENDOR_DIR) not in sys.path:
        sys.path.append(str(_VENDOR_DIR))
    if (_VENDOR_DIR / "policies").is_dir():
        os.environ.setdefault("POLICY_DOCS_DIR", str(_VENDOR_DIR / "policies"))
