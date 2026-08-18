"""SPEC 6.2: every way a policy can be defective ends in a refusal.

These are the tests that matter most, because they are the ones a permissive
implementation still passes the happy path with. Each case takes a conforming
document, breaks one thing, and asserts the break produces a refusal rather
than a skipped check.

Note what is *not* being tested: no code in `croissant_policy` decides any of
these. The parser rewrites each defect into a native condition the reference
gate already refuses on, and the gate does the refusing. The tests are checking
that the routing is complete, not that a second evaluator agrees with the first.
"""

from __future__ import annotations

import copy
import unittest

from support import corpus

from croissant_policy import emit, parse
from croissant_policy.reference import load_gate
from croissant_policy.validate import validate

_, _, gate_mod = load_gate()


def conditions_of(doc, action_name):
    for action in doc["cpol:policy"]["cpol:permissibleAction"]:
        if action["cpol:actionName"] == action_name:
            return action["cpol:condition"]
    raise KeyError(action_name)


class FailClosed(unittest.TestCase):
    def setUp(self):
        self.native = corpus()["raw-reads"]
        self.doc = emit.emit(self.native)
        # A request that is admitted by the intact document, so that every
        # failure below is caused by the defect and not by the request.
        self.action = "trim"
        self.context = {"minReadLength": 30, "platform": "illumina"}
        baseline = parse.authorize(self.doc, self.action, self.context)
        self.assertEqual(baseline.verdict, gate_mod.PERMIT)

    def refuse(self, doc, action=None, context=None):
        decision = parse.authorize(doc, action or self.action, context or self.context)
        self.assertEqual(decision.verdict, gate_mod.REFUSE, decision.reasons)
        return decision

    def test_operator_outside_the_closed_set(self):
        doc = copy.deepcopy(self.doc)
        conditions_of(doc, "trim")[0]["cpol:operator"] = "cpol:matches"
        decision = self.refuse(doc)
        self.assertEqual(decision.reason_class, gate_mod.CONDITION)
        self.assertIn("minReadLength", " ".join(decision.reasons))
        self.assertFalse(validate(doc).conforms)

    def test_condition_missing_its_name(self):
        doc = copy.deepcopy(self.doc)
        del conditions_of(doc, "trim")[0]["cpol:conditionName"]
        self.assertEqual(self.refuse(doc).reason_class, gate_mod.CONDITION)
        self.assertFalse(validate(doc).conforms)

    def test_condition_missing_its_operator(self):
        doc = copy.deepcopy(self.doc)
        del conditions_of(doc, "trim")[0]["cpol:operator"]
        self.assertEqual(self.refuse(doc).reason_class, gate_mod.CONDITION)
        self.assertFalse(validate(doc).conforms)

    def test_condition_missing_its_operand(self):
        doc = copy.deepcopy(self.doc)
        del conditions_of(doc, "trim")[0]["cpol:expected"]
        self.assertEqual(self.refuse(doc).reason_class, gate_mod.CONDITION)
        self.assertFalse(validate(doc).conforms)

    def test_condition_that_is_not_a_node(self):
        doc = copy.deepcopy(self.doc)
        conditions_of(doc, "trim")[0] = "minReadLength >= 20"
        self.assertEqual(self.refuse(doc).reason_class, gate_mod.CONDITION)

    def test_duplicate_condition_names_do_not_silently_collapse(self):
        # The native model keys conditions by name. Two nodes with one name
        # would drop a rule on the floor; the second one poisons the name.
        doc = copy.deepcopy(self.doc)
        duplicate = copy.deepcopy(conditions_of(doc, "trim")[0])
        duplicate["cpol:expected"] = 1
        conditions_of(doc, "trim").append(duplicate)
        decision = self.refuse(doc)
        self.assertEqual(decision.reason_class, gate_mod.CONDITION)
        self.assertIn("more than once", " ".join(decision.reasons))
        self.assertFalse(validate(doc).conforms)

    def test_fail_closed_not_declared_refuses_every_action(self):
        for value in (None, False, "true", 1):
            with self.subTest(failClosed=value):
                doc = copy.deepcopy(self.doc)
                if value is None:
                    del doc["cpol:policy"]["cpol:failClosed"]
                else:
                    doc["cpol:policy"]["cpol:failClosed"] = value
                self.assertFalse(validate(doc).conforms)
                for action in ("qc", "trim", "align"):
                    decision = parse.authorize(doc, action, self.context)
                    self.assertEqual(decision.verdict, gate_mod.REFUSE)
                    # Even for 'align', whose state precondition would fail
                    # first on an intact document: the document's defect is the
                    # more specific truth and must not be masked.
                    self.assertEqual(decision.reason_class, gate_mod.CONDITION)
                    self.assertIn("cpol:failClosed", " ".join(decision.reasons))

    def test_more_than_one_policy_admits_nothing(self):
        doc = copy.deepcopy(self.doc)
        doc["cpol:policy"] = [doc["cpol:policy"], copy.deepcopy(doc["cpol:policy"])]
        self.assertFalse(validate(doc).conforms)
        for action in ("qc", "trim", "align"):
            decision = parse.authorize(doc, action, self.context)
            self.assertEqual(decision.verdict, gate_mod.REFUSE)
            self.assertEqual(decision.reason_class, gate_mod.UNDECLARED)

    def test_a_document_with_no_policy_is_out_of_scope_not_permitted(self):
        doc = copy.deepcopy(self.doc)
        del doc["cpol:policy"]
        with self.assertRaises(parse.ProfileError):
            parse.authorize(doc, self.action, self.context)

    def test_every_condition_is_evaluated_even_after_the_first_failure(self):
        # SPEC 6.1 step 3. A record that lists only the failing rule cannot
        # show the others were checked.
        decision = parse.authorize(
            self.doc, "trim", {"minReadLength": 1, "platform": "nanopore"}
        )
        self.assertEqual(decision.reason_class, gate_mod.CONDITION)
        self.assertEqual(len(decision.conditions), 2)
        self.assertEqual(len(decision.reasons), 2)

    def test_passing_conditions_are_recorded_alongside_the_failing_one(self):
        decision = parse.authorize(
            self.doc, "trim", {"minReadLength": 1, "platform": "illumina"}
        )
        passed = [c.name for c in decision.conditions if c.passed]
        failed = [c.name for c in decision.conditions if not c.passed]
        self.assertEqual(passed, ["platform"])
        self.assertEqual(failed, ["minReadLength"])

    def test_an_empty_action_list_is_rejected_at_emit(self):
        native = copy.deepcopy(self.native)
        native["permissibleActions"] = []
        with self.assertRaises(emit.EmitError):
            emit.emit(native)


if __name__ == "__main__":
    unittest.main()
