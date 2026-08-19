"""Locating the reference evaluator.

The profile's central claim is that a policy expressed as Croissant produces
exactly the decisions the native descriptor produces. That claim is only worth
anything if both sides are decided by the *same* evaluator, so the gate is
imported from its own repository rather than vendored here. A vendored copy
would drift, and the first thing it would stop agreeing with is the 119 us
measurement it was copied from.

Resolution order for the gate's location:

1. `$NFGATE_ROOT`
2. a sibling checkout, `../ok-nfcore-admission-gate`

If neither exists the import fails loudly. Silently falling back to a local
reimplementation is the one behaviour that would make the test suite lie.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIBLING = _REPO_ROOT.parent / "ok-nfcore-admission-gate"


class ReferenceUnavailable(RuntimeError):
    """The reference gate could not be located or imported."""


def gate_root() -> Path:
    env = os.environ.get("NFGATE_ROOT")
    candidates = [Path(env)] if env else []
    candidates.append(_SIBLING)
    for c in candidates:
        if (c / "gate" / "gate.py").is_file():
            return c.resolve()
    raise ReferenceUnavailable(
        "cannot find ok-nfcore-admission-gate. Set NFGATE_ROOT to its checkout, "
        f"or place it next to this repository at {_SIBLING}. "
        "The evaluator is imported, never copied -- see the module docstring."
    )


_CACHE: tuple | None = None


def load_gate():
    """Import and return the gate modules: (descriptor, policy, gate).

    Memoised. Python caches the modules themselves, but re-executing three
    `import` statements per call is tens of microseconds, which is the same
    order as the thing bench/profile_overhead.py is trying to measure. An
    overhead figure that is mostly this function's own import bookkeeping
    would be a measurement of the harness.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    root = str(gate_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from gate import descriptor as descriptor_mod  # noqa: PLC0415
        from gate import gate as gate_mod  # noqa: PLC0415
        from gate import policy as policy_mod  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment failure
        raise ReferenceUnavailable(f"found {root} but could not import gate: {exc}") from exc
    _CACHE = (descriptor_mod, policy_mod, gate_mod)
    return _CACHE


def authorize(descriptor, action: str, context: dict):
    """The reference admission decision. No wrapper logic, on purpose."""
    _, _, gate_mod = load_gate()
    return gate_mod.authorize(descriptor, action, context)
