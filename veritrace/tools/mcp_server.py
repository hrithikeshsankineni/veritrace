"""Veritrace MCP-style tool server.

Exposes a registry of tools with JSON schemas, a routing layer that maps
natural-language action queries to the correct tool, and a verify-then-execute
gate that returns an ActionInfo.

This is an in-process tool dispatcher called by the responder agent when
intent == "action".  It follows the Model Context Protocol (MCP) naming
conventions: tools have a name, description, and parameter schema; execution
returns a structured result.
"""

from __future__ import annotations

from veritrace.schemas import ActionInfo
from veritrace.tools.actions import TOOL_SCHEMAS, execute, extract_parameters


# ---------------------------------------------------------------------------
# Tool routing — keyword scoring
# ---------------------------------------------------------------------------

_ROUTE_KEYWORDS: dict[str, list[str]] = {
    "lookup_coverage": [
        "look up", "check coverage", "what is covered", "is covered",
        "my copay", "what tier", "coverage for", "drug coverage",
        "formulary check", "covered for", "check my coverage",
    ],
    "file_inquiry": [
        "file", "submit", "create ticket", "open ticket", "inquiry",
        "appeal", "dispute", "request a review", "start a claim",
    ],
}


def _route_tool(query: str) -> str:
    """Map query text to the best-matching tool name via keyword scoring."""
    lower = query.lower()
    scores: dict[str, int] = {tool: 0 for tool in _ROUTE_KEYWORDS}
    for tool, kws in _ROUTE_KEYWORDS.items():
        scores[tool] = sum(1 for kw in kws if kw in lower)

    # Prefer lookup_coverage on ties (read-preferred safety default)
    return max(scores, key=lambda t: (scores[t], t == "lookup_coverage"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def dispatch(query: str, tenant_id: str) -> ActionInfo:
    """Route, extract parameters, verify, and execute a tool call.

    Returns an ActionInfo ready to embed in a TrustReceipt.
    The member_id is stripped from the returned parameters dict so it is
    never echoed back in the Trust Receipt (it will have been redacted by
    the safety layer before this point anyway).
    """
    tool_name = _route_tool(query)
    params = extract_parameters(tool_name, query)
    outcome = execute(tool_name, params)

    # Strip PII from the stored parameter snapshot
    safe_params = {k: v for k, v in params.items() if k != "member_id"}

    return ActionInfo(
        tool=tool_name,
        parameters=safe_params,
        verified=outcome["verified"],
        result=outcome["result"],
    )


def list_tools() -> list[dict]:
    """Return the tool registry (used by the /v1/tools API endpoint)."""
    return [
        {
            "name": name,
            "description": schema["description"],
            "mutates": schema["mutates"],
            "parameters": {
                pname: {k: v for k, v in pspec.items() if k != "pattern"}
                for pname, pspec in schema["parameters"].items()
            },
        }
        for name, schema in TOOL_SCHEMAS.items()
    ]
