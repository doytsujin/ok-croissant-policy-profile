"""Shared fixtures: the real descriptor corpus and a generated request matrix.

The corpus is the three descriptors from `ok-nfcore-admission-gate`, not
hand-written fixtures. Testing the profile against invented descriptors would
prove the profile is self-consistent; testing it against the descriptors that
gated a real pipeline run is what the equivalence claim is about.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from croissant_policy.reference import gate_root  # noqa: E402


def corpus() -> dict[str, dict]:
    """Every native descriptor in the reference repository, by dataset id."""
    out = {}
    for path in sorted((gate_root() / "descriptors").glob("*.json")):
        native = json.loads(path.read_text())
        out[native["datasetId"]] = native
    return out


# The request-matrix generator moved into the package (croissant_policy.requests)
# when bench/precedence.py needed it too. Re-exported here so the test modules
# that import it from support keep working.
from croissant_policy.requests import request_matrix  # noqa: E402,F401


def record(decision) -> dict:
    """A decision record with the timing removed, so two runs compare equal."""
    rec = decision.as_record()
    rec.pop("evalMicros", None)
    return rec
