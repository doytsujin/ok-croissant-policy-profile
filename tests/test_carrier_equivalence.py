"""C5: the carrier does not decide anything. The evaluation semantics does.

C1 shows that a policy expressed as Croissant decides what the native
descriptor decides. This shows something narrower and, for the argument about
why this profile exists at all, more useful: that expressing the same policy as
an ODRL Set in `sc:usageInfo` -- the carrier Croissant 1.1 itself recommends --
produces the same decision records, condition for condition.

Two consequences follow, and they are the reason this file exists.

The first is that "why not just use ODRL?" has an answer that is not an
opinion. It could have used ODRL; here it is using ODRL; the decisions are
identical. What the ODRL carrier does not bring with it is the evaluation
procedure, the bound, the failure semantics or the record -- those come from
this package either way, which is what the paper claims and what this test
checks.

The second is that the `cpol:` carrier is not load-bearing. If MLCommons
adopts a different spelling, the result survives the change.

As everywhere in this repository, equivalence is over the whole decision
record. Two carriers that agree on PERMIT/REFUSE and disagree on the refusal
class, the reasons, or the conditions they claim to have checked are not
equivalent in any sense an auditor would accept.
"""

from __future__ import annotations

import unittest

from support import corpus, record, request_matrix

from croissant_policy import emit, odrl, parse
from croissant_policy.reference import load_gate

descriptor_mod, _, gate_mod = load_gate()


class CarrierEquivalence(unittest.TestCase):
    def test_every_request_decides_identically_across_carriers(self):
        checked = 0
        for dataset_id, native in corpus().items():
            cpol_doc = emit.emit(native)
            odrl_doc = odrl.to_odrl(cpol_doc)
            cpol_desc = parse.to_descriptor(cpol_doc)
            odrl_desc = odrl.to_descriptor(odrl_doc)
            for action, context in request_matrix(native):
                with self.subTest(dataset=dataset_id, action=action, context=context):
                    a = gate_mod.authorize(cpol_desc, action, context)
                    b = gate_mod.authorize(odrl_desc, action, context)
                    self.assertEqual(record(a), record(b))
                checked += 1
        self.assertGreater(checked, 40, "request matrix collapsed")

    def test_the_matrix_exercises_every_outcome_on_the_odrl_carrier(self):
        """Agreement over a set of cases that are all the same is not evidence."""
        seen = set()
        for native in corpus().values():
            doc = odrl.emit(native)
            desc = odrl.to_descriptor(doc)
            for action, context in request_matrix(native):
                decision = gate_mod.authorize(desc, action, context)
                seen.add(decision.reason_class or "PERMIT")
        self.assertEqual(
            seen,
            {"PERMIT", gate_mod.UNDECLARED, gate_mod.STATE, gate_mod.CONDITION},
        )

    def test_the_odrl_carrier_round_trips_to_the_native_descriptor(self):
        """Stronger than deciding alike: the reconstructed model is the same one."""
        for native in corpus().values():
            cpol_doc = emit.emit(native)
            self.assertEqual(
                parse.to_native_json(cpol_doc),
                odrl.to_native_json(odrl.to_odrl(cpol_doc)),
            )

    def test_the_descriptive_half_is_identical_not_merely_equivalent(self):
        """The carrier swap must move the policy and nothing else.

        If the two documents differed anywhere outside the policy node, this
        would be a comparison of two documents rather than of two carriers, and
        a difference in decisions could come from the descriptive half.
        """
        for native in corpus().values():
            cpol_doc = emit.emit(native)
            odrl_doc = odrl.to_odrl(cpol_doc)
            left = {k: v for k, v in cpol_doc.items()
                    if k not in ("@context", "cpol:policy", "conformsTo")}
            right = {k: v for k, v in odrl_doc.items()
                     if k not in ("@context", "usageInfo", "conformsTo")}
            self.assertEqual(left, right)

    def test_four_of_five_operators_are_odrl_core(self):
        """The expressiveness objection to ODRL is not the real disagreement.

        Pinned as a test because it is a claim the paper makes: only `present`
        needs a minted operator, because ODRL defines no existence operator.
        If ODRL ever gains one, this test fails and the claim gets revisited.
        """
        core = [op for op, iri in odrl._TO_ODRL_OPERATOR.items()
                if iri.startswith(odrl.ODRL_NS)]
        minted = [op for op, iri in odrl._TO_ODRL_OPERATOR.items()
                  if not iri.startswith(odrl.ODRL_NS)]
        self.assertEqual(sorted(core),
                         ["cpol:equals", "cpol:in", "cpol:max", "cpol:min"])
        self.assertEqual(minted, ["cpol:present"])


class OdrlProfileFailsClosed(unittest.TestCase):
    """The one fail-closed property inherited from ODRL rather than argued for."""

    def _doc(self, native):
        return odrl.emit(native)

    def test_an_unrecognised_profile_identifier_refuses_everything(self):
        """ODRL Information Model 3.2: the processor MUST stop processing."""
        for native in corpus().values():
            doc = self._doc(native)
            doc["usageInfo"]["odrl:profile"] = {"@id": "https://example.org/some-other-profile"}
            desc = odrl.to_descriptor(doc)
            for action, _ in request_matrix(native):
                decision = gate_mod.authorize(desc, action, {})
                self.assertFalse(decision.permitted)

    def test_a_missing_profile_identifier_refuses_everything(self):
        for native in corpus().values():
            doc = self._doc(native)
            del doc["usageInfo"]["odrl:profile"]
            desc = odrl.to_descriptor(doc)
            decision = gate_mod.authorize(desc, "qc", {})
            self.assertFalse(decision.permitted)

    def test_an_operator_outside_the_closed_set_refuses(self):
        """What ODRL leaves open: an unknown operator inside a known profile."""
        for native in corpus().values():
            doc = self._doc(native)
            for permission in doc["usageInfo"]["odrl:permission"]:
                for constraint in permission.get("odrl:constraint", []):
                    if constraint["odrl:leftOperand"]["@id"] != odrl.LEFT_STATE:
                        constraint["odrl:operator"] = {"@id": odrl.ODRL_NS + "hasPart"}
            desc = odrl.to_descriptor(doc)
            for action in native.get("permissibleActions", []):
                if not action.get("conditions"):
                    continue
                decision = gate_mod.authorize(desc, action["name"], {})
                self.assertFalse(decision.permitted)

    def test_an_undeclared_failclosed_refuses(self):
        for native in corpus().values():
            doc = self._doc(native)
            del doc["usageInfo"]["cpolodrl:failClosed"]
            desc = odrl.to_descriptor(doc)
            for action in native.get("permissibleActions", []):
                decision = gate_mod.authorize(desc, action["name"], {})
                self.assertFalse(decision.permitted)


if __name__ == "__main__":
    unittest.main()
