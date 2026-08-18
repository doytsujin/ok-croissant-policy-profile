"""Project a policy onto agent-callable capabilities.

An agent does not read a dataset descriptor. It reads a tool list. This module
turns the policy layer into that tool list, in the shape a Model Context
Protocol client expects, so an agent registry can ingest data-side policy
without anyone transcribing it.

The transcription is the point. A registry entry written by hand says what
somebody believed the policy was on the day they wrote it, and drifts from
there silently. An entry derived from the document cannot drift, because
changing the policy changes the schema in the same commit.

The projection describes what will be checked. It never replaces the check:
`cpol:min` becomes `minimum` in the schema so a well-behaved caller can avoid a
refusal, and a caller that ignores the schema is still refused by the gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .parse import _as_list
from .vocab import OPERATORS

_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return _SLUG.sub("-", name.strip().lower()).strip("-")


def _schema_for(operator: str, expected):
    """One condition's operator -> its JSON Schema constraint.

    Returns (schema, required). `required` is False only for `present: false`,
    which is a constraint that the property be absent.
    """
    native = OPERATORS.get(operator)
    if native == "min":
        return {"type": "number", "minimum": expected}, True
    if native == "max":
        return {"type": "number", "maximum": expected}, True
    if native == "in":
        return {"enum": list(expected) if isinstance(expected, list) else [expected]}, True
    if native == "equals":
        return {"const": expected}, True
    if native == "present":
        if expected is False:
            return None, False
        return {}, True

    # An operator outside the closed set is a guaranteed refusal (SPEC 6.2).
    # The schema has to say so, or the capability advertises something callable
    # that can never be called. `not: {}` matches nothing, which is exactly the
    # truth about this parameter.
    return {
        "not": {},
        "description": (
            f"operator {operator!r} is outside the profile's closed set; "
            "any call naming this action is refused"
        ),
    }, True


def _describe(dataset: str, action_name: str, states: list[str]) -> str:
    sentence = f"Perform {action_name!r} on dataset {dataset!r}."
    if states:
        joined = ", ".join(repr(s) for s in states)
        sentence += f" Permitted only while the dataset is in state {joined}."
    else:
        sentence += " No state precondition."
    return sentence


def capability(dataset: str, action: dict) -> dict:
    """One `cpol:Action` node -> one MCP tool definition."""
    action_name = action.get("cpol:actionName", "")
    states = [s for s in _as_list(action.get("cpol:requiresState")) if isinstance(s, str)]

    properties: dict = {}
    required: list[str] = []
    forbidden: list[str] = []

    for node in _as_list(action.get("cpol:condition")):
        if not isinstance(node, dict):
            continue
        name = node.get("cpol:conditionName")
        if not isinstance(name, str) or not name:
            continue
        schema, is_required = _schema_for(node.get("cpol:operator"), node.get("cpol:expected"))
        if schema is None:
            forbidden.append(name)
            continue
        properties[name] = schema
        if is_required:
            required.append(name)

    input_schema: dict = {
        "type": "object",
        "properties": properties,
        # The gate ignores context keys no condition names, so the schema says
        # so rather than rejecting calls the gate would have admitted.
        "additionalProperties": True,
    }
    if required:
        input_schema["required"] = sorted(required)
    if forbidden:
        input_schema["not"] = {"anyOf": [{"required": [n]} for n in sorted(forbidden)]}

    return {
        "name": action.get("cpol:capabilityName") or f"{slugify(dataset)}.{action_name}",
        "description": action.get("cpol:description") or _describe(dataset, action_name, states),
        "inputSchema": input_schema,
    }


def project(doc: dict) -> list[dict]:
    """Profile document -> MCP tool list, one tool per permissible action."""
    dataset = doc.get("name", "")
    policies = _as_list(doc.get("cpol:policy"))
    if len(policies) != 1 or not isinstance(policies[0], dict):
        # Nothing coherent to advertise. An agent offered no tools calls none,
        # which is the right behaviour for a document that cannot be evaluated.
        return []
    actions = [a for a in _as_list(policies[0].get("cpol:permissibleAction")) if isinstance(a, dict)]
    return [capability(dataset, a) for a in actions]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="croissant_policy.capabilities",
        description="Project policy documents onto an MCP tool list",
    )
    ap.add_argument("documents", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    tools: list[dict] = []
    for path in args.documents:
        tools.extend(project(json.loads(path.read_text())))

    text = json.dumps({"tools": tools}, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"capabilities: {len(tools)} tools -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
