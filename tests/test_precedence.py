"""Experiment 2: the caller-side and data-side authorities, and precedence.

The claims under test are about the *relationship* between two policies, not
about either one, so most of these assert properties over the whole generated
request space rather than checking individual cases.

The caller side is designed, not measured — a model of the structure agent
control planes describe. What is not designed is the interaction: neither
authority was written to disagree with the other in any particular way, and the
disagreement classes fall out of running them together.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from support import corpus

from croissant_policy import conjunction, emit
from croissant_policy.caller import CallerScope, ScopeError, load_all
from croissant_policy.reference import load_gate
from croissant_policy.requests import request_matrix

_, _, gate_mod = load_gate()
CALLERS = Path(__file__).resolve().parent.parent / "examples" / "callers"


class CallerScopes(unittest.TestCase):
    def test_scopes_load(self):
        scopes = load_all(CALLERS)
        self.assertEqual(
            sorted(scopes), ["analyst-agent", "expired-agent", "pipeline-agent", "readonly-agent"]
        )

    def test_a_scope_is_decided_by_the_same_evaluator(self):
        # The control that makes precedence the only variable: if the two sides
        # used different evaluators, a disagreement could come from the
        # evaluators rather than from the policies.
        scope = load_all(CALLERS)["pipeline-agent"]
        native = scope.to_native_json()
        self.assertEqual(native["datasetId"], "pipeline-agent")
        self.assertEqual(native["state"], "ATTESTED")
        decision = scope.authorize("trim", {"platform": "illumina", "minReadLength": 30})
        self.assertEqual(decision.verdict, gate_mod.PERMIT)

    def test_lapsed_assurance_refuses_on_the_callers_own_lifecycle(self):
        scope = load_all(CALLERS)["expired-agent"]
        decision = scope.authorize("qc", {})
        self.assertEqual(decision.reason_class, gate_mod.STATE)

    def test_a_scope_missing_a_required_field_is_refused(self):
        for field in ("callerId", "version", "assurance"):
            with self.subTest(missing=field):
                obj = {"callerId": "a", "version": "1", "assurance": "ATTESTED"}
                del obj[field]
                with self.assertRaises(ScopeError):
                    CallerScope.from_json(obj)


class Precedence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scopes = load_all(CALLERS)
        cls.datasets = {k: (v, emit.emit(v)) for k, v in corpus().items()}
        cls.joints = [
            conjunction.decide(scope, doc, action, context)
            for scope in cls.scopes.values()
            for native, doc in cls.datasets.values()
            for action, context in request_matrix(native)
        ]

    def test_the_request_space_is_not_trivial(self):
        self.assertGreater(len(self.joints), 150)

    def test_both_authorities_refuse_things_the_other_permits(self):
        # P1. If either permit set were a subset of the other, precedence would
        # be a non-question and one of the two products would be redundant.
        classes = {j.agreement for j in self.joints}
        self.assertIn(conjunction.CALLER_ONLY_REFUSED, classes)
        self.assertIn(conjunction.DATA_ONLY_REFUSED, classes)
        self.assertIn(conjunction.AGREE_PERMIT, classes)
        self.assertIn(conjunction.AGREE_REFUSE, classes)

    def test_deny_overrides_never_admits_a_refused_request(self):
        # P2, the safety property, over the whole space rather than by example.
        for joint in self.joints:
            self.assertFalse(joint.unsafe_under(conjunction.DENY_OVERRIDES))

    def test_running_one_authority_alone_admits_refused_requests(self):
        # ...and the same property fails for both single-sided deployments,
        # which is the finding. Neither product is safe on its own terms.
        caller_only = [j for j in self.joints if j.unsafe_under(conjunction.CALLER_ONLY)]
        data_only = [j for j in self.joints if j.unsafe_under(conjunction.DATA_ONLY)]
        self.assertTrue(caller_only)
        self.assertTrue(data_only)

    def test_the_caller_cannot_reach_a_dataset_state_refusal(self):
        # The structural asymmetry. A caller-side plane permits, the dataset
        # refuses on its state, and no caller-side rule could have known.
        state_gaps = [
            j for j in self.joints
            if j.agreement == conjunction.DATA_ONLY_REFUSED
            and j.data.reason_class == gate_mod.STATE
        ]
        self.assertTrue(state_gaps)

    def test_the_dataset_cannot_reach_an_entitlement_refusal(self):
        # The mirror image: the caller is not entitled, and no descriptor can
        # say so because the profile has no identity model (SPEC section 8).
        entitlement_gaps = [
            j for j in self.joints
            if j.agreement == conjunction.CALLER_ONLY_REFUSED
            and j.caller.reason_class in (gate_mod.UNDECLARED, gate_mod.STATE)
        ]
        self.assertTrue(entitlement_gaps)

    def test_every_precedence_rule_produces_a_verdict(self):
        for joint in self.joints:
            for rule in conjunction.PRECEDENCE_RULES:
                self.assertIn(joint.effective(rule), (gate_mod.PERMIT, gate_mod.REFUSE))

    def test_prebuilt_descriptors_decide_identically(self):
        scope = self.scopes["pipeline-agent"]
        native, doc = self.datasets["raw-reads"]
        ctx = {"minReadLength": 30, "platform": "illumina"}
        a = conjunction.decide(scope, doc, "trim", ctx)
        b = conjunction.decide(
            scope, doc, "trim", ctx,
            data_descriptor=conjunction.to_descriptor(doc),
            caller_descriptor=scope.to_descriptor(),
        )
        self.assertEqual(a.as_record(), b.as_record())


class JointReceipt(unittest.TestCase):
    def setUp(self):
        self.scope = load_all(CALLERS)["analyst-agent"]
        native = corpus()["raw-reads"]
        self.doc = emit.emit(native)
        # The governance gap in one request: the caller's threshold is 10, the
        # dataset's is 20, and this asks for 15.
        self.joint = conjunction.decide(
            self.scope, self.doc, "trim", {"minReadLength": 15, "platform": "illumina"}
        )

    def test_the_disagreement_is_the_expected_one(self):
        self.assertEqual(self.joint.agreement, conjunction.DATA_ONLY_REFUSED)
        self.assertTrue(self.joint.disagreed)

    def test_one_receipt_names_both_authorities(self):
        record = self.joint.as_record()
        self.assertEqual(record["callerId"], "analyst-agent")
        self.assertEqual(record["datasetId"], "raw-reads")
        self.assertEqual(record["caller"]["verdict"], gate_mod.PERMIT)
        self.assertEqual(record["data"]["verdict"], gate_mod.REFUSE)
        self.assertEqual(record["verdict"], gate_mod.REFUSE)

    def test_the_receipt_carries_the_permitting_authority_too(self):
        # A joint record that keeps only the refusing half cannot show that the
        # other authority was consulted, which is the reason to have one record
        # rather than two.
        record = self.joint.as_record()
        self.assertTrue(record["caller"]["conditionsChecked"])
        self.assertTrue(all(c["passed"] for c in record["caller"]["conditionsChecked"]))
        self.assertTrue(any(not c["passed"] for c in record["data"]["conditionsChecked"]))

    def test_the_receipt_records_what_each_rule_would_have_done(self):
        record = self.joint.as_record()
        self.assertEqual(
            record["verdictsByPrecedence"][conjunction.CALLER_ONLY], gate_mod.PERMIT
        )
        self.assertEqual(
            record["verdictsByPrecedence"][conjunction.DENY_OVERRIDES], gate_mod.REFUSE
        )

    def test_the_receipt_is_serialisable(self):
        json.dumps(self.joint.as_record())


if __name__ == "__main__":
    unittest.main()
