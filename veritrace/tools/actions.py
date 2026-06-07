"""Veritrace tool actions — two verified tools behind a gate.

Tools
-----
lookup_coverage  (READ)  : Look up a member's drug coverage from the DB.
file_inquiry     (WRITE) : File a new coverage inquiry ticket.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "synthetic" / "records.sqlite"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Tool registry — JSON-schema-style parameter specs
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: dict[str, dict] = {
    "lookup_coverage": {
        "description": "Look up drug coverage details for a member from the plan database.",
        "parameters": {
            "member_id": {
                "type": "string",
                "required": True,
                "pattern": r"^[A-Z]{1,4}-\d{4,}$",
                "description": "Member identifier (e.g. MBR-100042)",
            },
            "drug_name": {
                "type": "string",
                "required": True,
                "description": "Name of the drug to look up",
            },
        },
        "mutates": False,
    },
    "file_inquiry": {
        "description": "File a coverage inquiry ticket on behalf of a member.",
        "parameters": {
            "member_id": {
                "type": "string",
                "required": True,
                "pattern": r"^[A-Z]{1,4}-\d{4,}$",
                "description": "Member identifier",
            },
            "description": {
                "type": "string",
                "required": True,
                "max_length": 500,
                "description": "Description of the inquiry",
            },
        },
        "mutates": True,
    },
}


# ---------------------------------------------------------------------------
# Parameter extraction from natural language
# ---------------------------------------------------------------------------

_MEMBER_ID_RE = re.compile(r"\b([A-Z]{1,4}-\d{4,})\b")
_DRUG_RE = re.compile(
    r"\b(atorvastatin|rosuvastatin|simvastatin|sertraline|bupropion|"
    r"lisinopril|metformin|omeprazole|amlodipine)\b",
    re.IGNORECASE,
)


def extract_parameters(tool_name: str, query: str) -> dict[str, Any]:
    """Best-effort parameter extraction from natural language query."""
    params: dict[str, Any] = {}

    m = _MEMBER_ID_RE.search(query)
    if m:
        params["member_id"] = m.group(1)

    if tool_name == "lookup_coverage":
        d = _DRUG_RE.search(query)
        if d:
            params["drug_name"] = d.group(1).lower()
        else:
            match = re.search(r"\bfor\s+(\w+)", query, re.IGNORECASE)
            if match:
                params["drug_name"] = match.group(1).lower()

    if tool_name == "file_inquiry":
        params["description"] = query[:300]

    return params


# ---------------------------------------------------------------------------
# Verification gate
# ---------------------------------------------------------------------------

def verify(tool_name: str, params: dict[str, Any]) -> tuple[bool, str]:
    """Verify that a tool call is well-formed and safe to execute.

    Returns (ok, reason).  If ok=False the action is rejected before execution.
    """
    if tool_name not in TOOL_SCHEMAS:
        return False, f"Unknown tool: {tool_name!r}"

    schema = TOOL_SCHEMAS[tool_name]
    for pname, pspec in schema["parameters"].items():
        if pspec.get("required") and pname not in params:
            return False, f"Missing required parameter: {pname}"
        val = params.get(pname)
        if val is None:
            continue
        if "pattern" in pspec and not re.fullmatch(pspec["pattern"], str(val)):
            return False, f"Invalid format for {pname}: {val!r}"
        if "max_length" in pspec and len(str(val)) > pspec["max_length"]:
            return False, f"Parameter {pname} exceeds max length of {pspec['max_length']}"

    return True, "verified"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _lookup_coverage(member_id: str, drug_name: str) -> str:
    if not _DB_PATH.exists():
        return "Coverage database unavailable — please contact Member Services."

    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT first_name, last_name, plan FROM members WHERE member_id = ?",
            (member_id,),
        )
        row = cur.fetchone()
        if not row:
            return f"Member {member_id} was not found in the system."

        name = f"{row['first_name']} {row['last_name']}"
        plan = row["plan"]

        cur = conn.execute(
            "SELECT covered, tier, copay_usd, pa_required FROM coverage_records "
            "WHERE member_id = ? AND lower(drug_name) LIKE ?",
            (member_id, f"%{drug_name.lower()}%"),
        )
        rec = cur.fetchone()

        if rec:
            cov = "covered" if rec["covered"] else "not covered"
            pa = " · Prior authorization required" if rec["pa_required"] else ""
            return (
                f"{name} ({member_id}, {plan}): "
                f"{drug_name.title()} is {cov} at Tier {rec['tier']}, "
                f"copay ${rec['copay_usd']:.2f}.{pa}"
            )
        else:
            return (
                f"{name} ({member_id}): no specific coverage record for "
                f"{drug_name.title()} under {plan}. "
                "Please consult the plan formulary or contact Member Services."
            )
    finally:
        conn.close()


def _file_inquiry(member_id: str, description: str) -> str:
    if not _DB_PATH.exists():
        return "Ticketing system unavailable — please contact Member Services directly."

    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT first_name, last_name FROM members WHERE member_id = ?",
            (member_id,),
        )
        row = cur.fetchone()
        if not row:
            return f"Cannot file ticket — member {member_id} not found."

        from datetime import datetime, timezone
        from uuid import uuid4

        ticket_id = f"TKT-{uuid4().hex[:4].upper()}"
        created = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT INTO tickets "
            "(ticket_id, member_id, type, status, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, member_id, "coverage_inquiry", "open", description[:500], created),
        )
        conn.commit()

        name = f"{row['first_name']} {row['last_name']}"
        return (
            f"Inquiry ticket {ticket_id} filed for {name} ({member_id}). "
            "Status: open. A Member Services representative will follow up "
            "within 2 business days."
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public executor
# ---------------------------------------------------------------------------

_EXECUTORS: dict[str, Any] = {
    "lookup_coverage": lambda p: _lookup_coverage(p["member_id"], p["drug_name"]),
    "file_inquiry": lambda p: _file_inquiry(p["member_id"], p["description"]),
}


def execute(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Verify then execute a tool call.

    Returns a dict with keys: verified (bool), result (str), error (str|None).
    """
    ok, reason = verify(tool_name, params)
    if not ok:
        return {"verified": False, "result": f"Action rejected: {reason}", "error": reason}
    try:
        result = _EXECUTORS[tool_name](params)
        return {"verified": True, "result": result, "error": None}
    except Exception as exc:
        return {"verified": False, "result": f"Tool execution failed: {exc}", "error": str(exc)}
