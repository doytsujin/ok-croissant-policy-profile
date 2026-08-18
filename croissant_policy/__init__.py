"""A policy profile for Croissant dataset descriptors.

The profile is specified in SPEC.md. This package is the reference tooling for
it: emit a conforming document from a native descriptor, parse one back,
validate conformance, and project the policy onto agent-callable capabilities.

Deliberately absent: an evaluator. Admission decisions are made by the gate in
`dk-nfcore-admission-gate`, imported rather than copied, so that a decision
taken through the profile is taken by the same code that produced the measured
122 microsecond figure. See `reference.py`.
"""

from .vocab import PROFILE_IRI, PROFILE_VERSION, OPERATORS  # noqa: F401

__all__ = ["PROFILE_IRI", "PROFILE_VERSION", "OPERATORS"]
