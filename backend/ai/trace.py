"""Turns a PydanticAI run's message history into a flat, human-readable trace of
which tools were called and what came back — used to power the "Behind the scenes"
panel. This is pure extraction over structured data already produced by the run;
it never calls the model again and never changes what happened.
"""

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

MAX_RESULT_CHARS = 300


class TraceStep(BaseModel):
    helper: str
    tool: str | None = None
    args: dict | None = None
    result: str
    # Populated only on the one synthetic step per agent invocation (not on each
    # individual tool call within it, since those share — not add to — the parent
    # agent call's single token/cost total) so "Behind the scenes" can show real
    # per-agent cost, not just one combined number for the whole request.
    input_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _truncate(value: object) -> str:
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "…"


def extract_trace(helper: str, messages: list[ModelMessage]) -> list[TraceStep]:
    """One TraceStep per tool call/return pair in this run, in call order. Call
    and return parts are matched by `tool_call_id` since they live in different
    messages (the call in a ModelResponse, the return in the next ModelRequest)."""
    calls: dict[str, dict] = {}
    order: list[str] = []
    returned_ids: set[str] = set()
    results: dict[str, str] = {}

    for message in messages:
        for part in message.parts:
            if part.part_kind == "tool-call":
                calls[part.tool_call_id] = {"tool_name": part.tool_name, "args": part.args_as_dict()}
                order.append(part.tool_call_id)
            elif part.part_kind == "tool-return":
                returned_ids.add(part.tool_call_id)
                results[part.tool_call_id] = _truncate(part.content)

    steps: list[TraceStep] = []
    for call_id in order:
        call = calls[call_id]
        result = results.get(call_id, "(no result recorded)")
        steps.append(TraceStep(helper=helper, tool=call["tool_name"], args=call["args"], result=result))
    return steps
