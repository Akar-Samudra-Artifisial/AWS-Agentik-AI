"""Build the Strands agent for one turn: Bedrock model, system prompt and bound tools.

Each tool from ``agent.tools`` is bound to the turn's ``ToolContext`` (so the model never
sees a case id or recipient), wrapped to record ``{tool, ok}`` for the invocation
response, then exposed through the Strands ``@tool`` decorator, which builds the tool
spec from the signature and the docstring the LLM reads.
"""

from __future__ import annotations

import functools
import inspect
from pathlib import Path
from typing import Any, get_type_hints

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.decorator import DecoratedFunctionTool

from .config import get_param
from .context import ToolContext
from .tools import TOOL_FUNCTIONS
from .tools.registry import ToolFn, bind_tool

__all__ = [
    "MODEL_ID_ENV",
    "MODEL_ID_PARAM",
    "SYSTEM_PROMPT_PATH",
    "build_agent",
    "build_model",
    "build_strands_tools",
    "load_system_prompt",
    "resolve_model_id",
]

MODEL_ID_ENV = "BEDROCK_MODEL_ID"
MODEL_ID_PARAM = "bedrock/model_id"
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_id.md"
# Short, deterministic customer-service replies.
_TEMPERATURE = 0.2
_MAX_TOKENS = 2048


@functools.lru_cache(maxsize=1)
def load_system_prompt(path: Path = SYSTEM_PROMPT_PATH) -> str:
    """Load ``prompts/system_id.md`` once per process (AG-004)."""
    return path.read_text(encoding="utf-8").strip()


def resolve_model_id() -> str:
    """Model id from ``BEDROCK_MODEL_ID`` or SSM ``<prefix>/bedrock/model_id``."""
    return get_param(MODEL_ID_PARAM, MODEL_ID_ENV)


def build_model(model_id: str | None = None) -> BedrockModel:
    """Bedrock model used by the agent; region comes from the boto3 session/env."""
    return BedrockModel(
        model_id=model_id or resolve_model_id(),
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    )


def _strands_tool(fn: ToolFn, ctx: ToolContext, actions: list[dict[str, Any]]) -> Any:
    target = inspect.unwrap(fn)
    bound = bind_tool(fn, ctx)

    @functools.wraps(bound)
    def recorded(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = bound(*args, **kwargs)
        actions.append({"tool": target.__name__, "ok": bool(result.get("ok"))})
        return result

    # Tool modules use postponed annotations; resolve them against the defining module
    # so Strands can build the input schema from real types.
    hints = get_type_hints(target, include_extras=True)
    recorded.__annotations__ = {k: v for k, v in hints.items() if k != "ctx"}
    params = list(inspect.signature(target).parameters.values())[1:]
    recorded.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [p.replace(annotation=hints.get(p.name, p.annotation)) for p in params],
        return_annotation=hints.get("return", inspect.Signature.empty),
    )
    return tool(recorded)


def build_strands_tools(
    ctx: ToolContext, actions: list[dict[str, Any]]
) -> list[DecoratedFunctionTool[..., dict[str, Any]]]:
    """All 11 tools bound to ``ctx``; every call appends ``{tool, ok}`` to ``actions``."""
    return [_strands_tool(fn, ctx, actions) for fn in TOOL_FUNCTIONS]


def build_agent(
    ctx: ToolContext,
    actions: list[dict[str, Any]],
    *,
    model: Any | None = None,
) -> Agent:
    """Fresh agent per turn; conversation history is passed in the prompt, not memory."""
    return Agent(
        model=model if model is not None else build_model(),
        tools=build_strands_tools(ctx, actions),
        system_prompt=load_system_prompt(),
        callback_handler=None,
    )
