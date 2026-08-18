"""C1: a policy expressed as Croissant decides exactly what the native one does.

Equivalence is checked on the whole decision record, not on the verdict. Two
evaluators that agree on PERMIT/REFUSE and disagree on the refusal class, the
reasons, or the conditions they say they checked are not equivalent in any
sense an auditor would accept.
"""

from __future__ import annotations

import unittest

from support import corpus, record, request_matrix

from croissant_policy import emit, parse
from croissant_policy.reference import load_gate

descriptor_mod, _, gate_mod = load_gate()


class DecisionEquivalence(unittest.TestCase):
    def test_every_request_decides_identically(self):
        checked = 0
        for dataset_id, native in corpus().items():
            doc = emit.emit(native)
            native_desc = descriptor_mod.Descriptor.from_json(native)
            profile_desc = parse.to_descriptor(doc)
            for action, context in request_matrix(native):
                with self.subTest(dataset=dataset_id, action=action, context=context):
                    a = gate_mod.authorize(native_desc, action, context)
                    b = gate_mod.authorize(profile_desc, action, context)
                    self.assertEqual(record(a), record(b))
                checked += 1
        # A guard against the matrix silently emptying and the test passing
        # because it compared nothing.
        self.assertGreater(checked, 40, "request matrix collapsed")

    def test_the_matrix_exercises_every_outcome(self):
        seen = set()
        for native in corpus().values():
            doc = emit.emit(native)
            desc = parse.to_descriptor(doc)
            for action, context in request_matrix(native):
                decision = gate_mod.authorize(desc, action, context)
                seen.add(decision.reason_class or "PERMIT")
        self.assertEqual(
            seen,
            {"PERMIT", gate_mod.UNDECLARED, gate_mod.STATE, gate_mod.CONDITION},
            "equivalence is only meaningful if every outcome occurs in the matrix",
        )

    def test_conditions_are_reported_in_the_same_order(self):
        # gate/policy.py evaluates sorted by condition name; the emitter sorts
        # too. A record that lists conditions in a different order than they
        # were checked is a small lie with a long debugging tail.
        for native in corpus().values():
            doc = emit.emit(native)
            desc = parse.to_descriptor(doc)
            for action in native.get("permissibleActions", []):
                decision = gate_mod.authorize(desc, action["name"], {})
                names = [c.name for c in decision.conditions]
                self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
