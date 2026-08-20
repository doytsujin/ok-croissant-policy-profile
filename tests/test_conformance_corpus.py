"""Specification coverage: native, cpol: and ODRL agree across the grammar.

C1 establishes that a policy expressed as Croissant decides what the native
descriptor decides, and C5 that the ODRL carrier decides the same. Both are
established on the deployment corpus -- three descriptors that gated a real
nf-core run -- which is the right evidence that this works in front of real
execution and thin evidence about the features the specification defines.

This module runs the same comparison over a corpus generated from the profile's
own grammar. The point is not that there are more documents, and it is not that
the space of conforming documents has been exhausted -- it has not, and with
arbitrary operands and cardinalities it could not be. The point is that the
corpus can say which *named features* it covers: every operator in the closed
set, every refusal class, every conformance clause, both carriers, and each
structural shape the specification allows -- multi-condition actions, multi-action
policies, lifecycle-state preconditions, wrong-typed operands, and the nine ways
the specification says a document can be wrong.

Two things this corpus is not, stated here so no test below is read as claiming
them. It is not evidence about which policies people write; rates computed over
it are properties of the generator. And it carries no timing: performance is
measured on the deployment corpus, where the descriptors are real.

The coverage claim is checked twice over. `test_coverage_is_declared` reads the
tags, which is assertion. `test_coverage_is_observed` collects the verdicts and
refusal classes the corpus actually produces when run, which is evidence. A tag
that no execution corroborates is a claim the corpus does not support, and the
second test is what would catch it.
"""

from __future__ import annotations

import json
import unittest

from support import record, request_matrix

from croissant_policy import conformance, emit, odrl, parse, validate
from croissant_policy.reference import load_gate

descriptor_mod, _, gate_mod = load_gate()

VALID = conformance.valid_cases()
DEFECTS = conformance.defect_cases()


def _documents(case):
    """The three representations of one valid case."""
    cpol_doc = emit.emit(case.native)
    return (
        descriptor_mod.Descriptor.from_json(case.native),
        parse.to_descriptor(cpol_doc),
        odrl.to_descriptor(odrl.to_odrl(cpol_doc)),
    )


class ThreeRepresentationsAgree(unittest.TestCase):
    def test_all_three_decide_identically_across_the_grammar(self):
        checked = 0
        for case in VALID:
            native_desc, cpol_desc, odrl_desc = _documents(case)
            for action, context in request_matrix(case.native):
                with self.subTest(case=case.id, action=action, context=context):
                    a = record(gate_mod.authorize(native_desc, action, context))
                    b = record(gate_mod.authorize(cpol_desc, action, context))
                    c = record(gate_mod.authorize(odrl_desc, action, context))
                    self.assertEqual(a, b, "native and cpol: disagree")
                    self.assertEqual(b, c, "cpol: and ODRL disagree")
                checked += 1
        # The corpus is generated, so an empty or collapsed matrix would make
        # every assertion above vacuous and the suite would still pass.
        self.assertGreater(checked, 150, "conformance request matrix collapsed")

    def test_the_native_model_round_trips_through_both_carriers(self):
        """Stronger than agreeing: the reconstructed descriptor is the same one."""
        for case in VALID:
            with self.subTest(case=case.id):
                cpol_doc = emit.emit(case.native)
                self.assertEqual(
                    parse.to_native_json(cpol_doc),
                    odrl.to_native_json(odrl.to_odrl(cpol_doc)),
                )


class ValidDocumentsConform(unittest.TestCase):
    def test_every_valid_case_passes_the_conformance_validator(self):
        for case in VALID:
            with self.subTest(case=case.id):
                report = validate.validate(emit.emit(case.native))
                self.assertEqual(
                    report.errors, [], f"{case.id} is generated from the grammar "
                    "and must satisfy the clauses that grammar encodes")

    def test_stripping_any_valid_case_leaves_a_croissant_dataset(self):
        for case in VALID:
            with self.subTest(case=case.id):
                bare = validate.strip(emit.emit(case.native))
                self.assertEqual(bare["@type"], "sc:Dataset")
                self.assertNotIn("cpol", json.dumps(bare))


class DefectsRefuseRatherThanDecide(unittest.TestCase):
    """The whole defect space, evaluated and not merely validated.

    A defect a validator reports and an evaluator ignores is precisely the
    failure this profile exists to prevent, so every case here is put through
    `authorize` and required to refuse.
    """

    def test_no_defect_document_permits_anything_in_either_carrier(self):
        for case in DEFECTS:
            doc = case.mutate(emit.emit(case.native))
            with self.subTest(case=case.id, defect=case.defect):
                cpol_desc = parse.to_descriptor(doc)
                for action, context in request_matrix(case.native):
                    decision = gate_mod.authorize(cpol_desc, action, context)
                    self.assertFalse(
                        decision.permitted,
                        f"{case.id} permitted {action!r} despite: {case.defect}")

    def test_the_defect_survives_into_the_odrl_carrier(self):
        """A carrier that launders a defect would be worse than no carrier.

        Over the full request matrix, including the satisfying context. An
        earlier version of this test passed the empty context only, which
        refuses for the wrong reason on almost any policy and hid a case where
        the ODRL document was not defective at all.
        """
        for case in DEFECTS:
            if case.no_odrl_form:
                continue
            doc = case.mutate(emit.emit(case.native))
            with self.subTest(case=case.id, defect=case.defect):
                odrl_desc = odrl.to_descriptor(odrl.to_odrl(doc))
                for action, context in request_matrix(case.native):
                    self.assertFalse(
                        gate_mod.authorize(odrl_desc, action, context).permitted,
                        f"{case.id} permitted through the ODRL carrier: {case.defect}")

    def test_the_two_defects_without_an_odrl_form_say_why(self):
        """Skipping a case is only honest if the corpus records the reason."""
        without = {c.id: c.no_odrl_form for c in DEFECTS if c.no_odrl_form}
        self.assertEqual(
            sorted(without), ["defect-no-profile-claim", "defect-two-policies"])
        for case_id, reason in without.items():
            self.assertTrue(reason and len(reason) > 20, case_id)

    def test_every_defect_is_reported_by_the_conformance_validator(self):
        for case in DEFECTS:
            doc = case.mutate(emit.emit(case.native))
            with self.subTest(case=case.id, defect=case.defect):
                self.assertNotEqual(
                    validate.validate(doc).errors, [],
                    f"{case.id} should be reported: {case.defect}")


class CoverageIsWhatIsReported(unittest.TestCase):
    def test_coverage_is_declared(self):
        cov = conformance.coverage()
        self.assertEqual(cov["operator"], ["equals", "in", "max", "min", "present"])
        self.assertEqual(cov["carrier"], ["cpol", "odrl"])
        self.assertEqual(cov["clause"], ["1", "2", "3", "4", "5"])
        for shape in ("multi-condition", "multi-action", "state-precondition",
                      "wrong-datatype", "strip", "defect"):
            self.assertIn(shape, cov["shape"])

    def test_coverage_is_observed(self):
        """Every outcome the corpus claims is one some request actually produced.

        Tags are written by hand and could drift from what the documents do.
        This collects the verdicts the corpus produces when run, and requires
        that PERMIT and all three refusal classes appear among them.
        """
        seen = set()
        for case in VALID:
            _, cpol_desc, _ = _documents(case)
            for action, context in request_matrix(case.native):
                decision = gate_mod.authorize(cpol_desc, action, context)
                seen.add(decision.reason_class or "PERMIT")
        self.assertEqual(
            seen,
            {"PERMIT", gate_mod.UNDECLARED, gate_mod.STATE, gate_mod.CONDITION},
            "the corpus claims to cover every refusal class; this is what it reached",
        )

    def test_every_operator_is_reached_by_a_decision_not_only_declared(self):
        """An operator present in a document but never evaluated is not covered."""
        reached = set()
        for case in VALID:
            _, cpol_desc, _ = _documents(case)
            for action, context in request_matrix(case.native):
                decision = gate_mod.authorize(cpol_desc, action, context)
                for condition in decision.conditions:
                    reached.add(condition.operator)
        # gate/policy.py reports operators in its own notation.
        for operator in (">=", "<=", "in", "==", "present"):
            self.assertIn(operator, reached, f"{operator} never evaluated")

    def test_the_corpus_makes_no_performance_claim(self):
        """Guards the separation the paper's evaluation section rests on."""
        manifest = conformance.write(outdir=None, emit_documents=False)
        self.assertIn("no timing", manifest["purpose"])
        self.assertNotIn("micros", json.dumps(manifest).lower())


if __name__ == "__main__":
    unittest.main()
